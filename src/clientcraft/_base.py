"""
Shared utilities for sync and async API clients.

This module contains the common infrastructure that both sync and async clients share:
- Request/response handling utilities
- Generic base client class with __init_subclass__ processing
- Generic endpoint descriptor parameterized by bound endpoint type
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, get_type_hints
from urllib.parse import urlencode

from pydantic import BaseModel

from ._endpoints import extract_endpoint_info
from ._responses import BytesResponse, TextResponse
from ._types import EndpointInfo, ModelDumpMode, RequestStyle, ResponseStyle
from .backends import HttpResponse

# An immutable status-code -> DomainError mapping. Using a read-only mapping (not a
# plain dict) keeps client-wide ``errors`` declarations immutable and lint-clean.
ErrorMap = MappingProxyType

# ---------------------------------------------------------------------------
# HTTP Error
# ---------------------------------------------------------------------------


class HttpError(Exception):
    """HTTP error with status code, response content, and the failed endpoint."""

    def __init__(
        self,
        status_code: int,
        content: bytes,
        headers: dict[str, str] | None = None,
        endpoint_info: EndpointInfo | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.endpoint_info = endpoint_info
        super().__init__(f"HTTP {status_code}: {content.decode('utf-8', errors='replace')}")


class DomainError(Exception):
    """Base class for domain errors translated from HTTP errors.

    Subclass this to define application-specific exceptions, then map HTTP status
    codes to them declaratively — per endpoint via :class:`~clientcraft.Raises`
    metadata, or per client via the ``errors`` class attribute.

    The mapped subclass constructs itself from the :class:`HttpError` via
    :meth:`from_http_error`. The default builds an instance carrying the original
    error on ``.http_error``; override it to parse the response body::

        class ValidationError(DomainError):
            @classmethod
            def from_http_error(cls, error: HttpError) -> "DomainError":
                payload = json.loads(error.content)
                exc = cls(payload["message"])
                exc.http_error = error
                return exc
    """

    #: The underlying HTTP error this domain error was translated from.
    http_error: HttpError | None = None

    @classmethod
    def from_http_error(cls, error: HttpError) -> DomainError:
        """Build a domain error instance from an :class:`HttpError`.

        The default implementation constructs ``cls(str(error))`` and attaches the
        original error on ``.http_error``. Override in subclasses that need to read
        the response body or take a different constructor signature.
        """
        exc = cls(str(error))
        exc.http_error = error
        return exc


# ---------------------------------------------------------------------------
# Request Preparation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedRequest:
    """
    A fully prepared HTTP request ready to be sent.

    Separating preparation from execution enables:
    - Easy testing (inspect the request before sending)
    - Middleware/interceptors
    - Retries with the same prepared request
    """

    method: str
    url: str
    content: bytes | None
    headers: dict[str, str]


def extract_path_params(path_template: str) -> set[str]:
    """Extract parameter names from a path template like '/users/{user_id}'."""
    return set(re.findall(r"\{(\w+)\}", path_template))


def serialize_query_value(value: object) -> str:
    """Serialize a value for use in query string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value)


def prepare_request(
    request: BaseModel | None,
    endpoint_info: EndpointInfo,
    path_params: set[str],
    base_url: str,
    default_headers: dict[str, str],
    model_dump_mode: ModelDumpMode = "json",
) -> PreparedRequest:
    """Build a PreparedRequest from the endpoint info and request data."""
    # A None request means the endpoint takes no parameters at all.
    request_dict = request.model_dump(mode=model_dump_mode, exclude_none=True) if request is not None else {}

    # Build URL with path interpolation
    url_path = endpoint_info.path
    for param in path_params:
        if param not in request_dict:
            raise ValueError(f"Path parameter '{param}' not found in request")
        url_path = url_path.replace(f"{{{param}}}", str(request_dict[param]))

    url = f"{base_url.rstrip('/')}/{url_path.lstrip('/')}"

    # Serialize based on request_style (from endpoint metadata, not HTTP method)
    content: bytes | None = None

    if endpoint_info.request_style == RequestStyle.QUERY:
        # Add non-path params to query string
        query_params = {k: serialize_query_value(v) for k, v in request_dict.items() if k not in path_params}
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

    elif endpoint_info.request_style == RequestStyle.BODY:
        # Serialize non-path params to JSON body
        body_dict = {k: v for k, v in request_dict.items() if k not in path_params}
        if body_dict:
            content = json.dumps(body_dict).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **default_headers,
    }

    return PreparedRequest(
        method=endpoint_info.method.name,
        url=url,
        content=content,
        headers=headers,
    )


def parse_response(
    response: HttpResponse,
    endpoint_info: EndpointInfo,
    response_type: type[BaseModel] | None,
) -> BaseModel | dict[str, Any] | list[Any] | None:
    """Parse response based on response_style."""
    style = endpoint_info.response_style

    if style == ResponseStyle.NONE:
        # No body expected - return None
        return None

    if style == ResponseStyle.TEXT:
        # Return text content
        return TextResponse(content=response.content.decode("utf-8"))

    if style == ResponseStyle.BYTES:
        # Return raw bytes
        return BytesResponse(content=response.content)

    # Default: JSON
    if response_type is not None:
        # Handle empty body gracefully for JSON
        if not response.content or response.content.strip() == b"":
            # If response type has no required fields, return empty instance
            # Otherwise this will raise a validation error (which is correct)
            return response_type.model_validate({})
        return response_type.model_validate_json(response.content)

    # No response type specified - return raw dict/list
    if not response.content or response.content.strip() == b"":
        return None
    result: dict[str, Any] | list[Any] = json.loads(response.content)
    return result


# ---------------------------------------------------------------------------
# Generic Base Client
# ---------------------------------------------------------------------------


class BaseAPIClient[Backend]:
    """
    Generic base class for declarative API clients.

    This handles all the shared logic for both sync and async clients:
    - __init_subclass__ processing of type hints
    - __init__ with base_url, backend, headers, timeout

    The Backend type parameter allows subclasses to specify their backend type.
    Concrete subclasses must define `_descriptor_factory` to create the appropriate
    descriptor type (sync or async).
    """

    # Subclasses must set this to their descriptor factory
    _descriptor_factory: type[EndpointDescriptor[Any]]

    # Client-wide declarative error mapping: status code -> DomainError subclass.
    # Applied when no per-endpoint ``Raises`` mapping matches. Set it in a subclass
    # to opt into domain-error translation across all endpoints::
    #
    #     errors = ErrorMap({429: RateLimited, 500: ServerError})
    #
    # ``ErrorMap`` is a read-only mapping, so the declaration stays immutable.
    errors: Mapping[int, type[DomainError]] = MappingProxyType({})

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Process Annotated type hints and create endpoint descriptors."""
        super().__init_subclass__(**kwargs)

        # Skip processing if this is still an abstract base
        if not hasattr(cls, "_descriptor_factory"):
            return

        try:
            hints = get_type_hints(cls, include_extras=True)
        except Exception:
            hints = {}

        for name, hint in hints.items():
            extracted = extract_endpoint_info(hint)

            if extracted is not None:
                descriptor = cls._descriptor_factory(
                    endpoint_info=extracted.info,
                    request_type=extracted.request_type,
                    response_type=extracted.response_type,
                    error_map=extracted.error_map,
                )
                setattr(cls, name, descriptor)

    def __init__(
        self,
        base_url: str,
        backend: Backend,
        *,
        default_headers: dict[str, str] | None = None,
        default_timeout: float | None = None,
        model_dump_mode: ModelDumpMode = "json",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._backend = backend
        self._default_headers = default_headers or {}
        self._default_timeout = default_timeout
        self._model_dump_mode = model_dump_mode

    def handle_error(self, error: HttpError) -> None:
        """Handle an HTTP error response (status >= 400).

        Called whenever an endpoint receives an error status code, for both sync
        and async clients. Override this in a subclass to translate HTTP errors
        into domain-specific exceptions.

        ``error`` is the pre-built :class:`HttpError` carrying the status code,
        content, headers, and ``endpoint_info`` (path, method) identifying which
        endpoint failed, so handling can branch per endpoint.

        The default implementation raises ``error``. Overrides should raise as
        well; returning normally suppresses the error and causes the endpoint to
        return ``None``, which is rarely what you want.

        Example::

            class MyAPI(APIClient):
                def handle_error(self, error):
                    if error.status_code == 404:
                        raise ResourceNotFound(error.endpoint_info.path) from error
                    super().handle_error(error)
        """
        raise error


# ---------------------------------------------------------------------------
# Generic Endpoint Descriptor
# ---------------------------------------------------------------------------


@dataclass
class EndpointDescriptor[ClientT: BaseAPIClient[Any]]:
    """
    Generic descriptor that creates bound endpoint callables.

    Subclasses override `_create_bound_endpoint` to return the appropriate
    sync or async bound endpoint type.
    """

    endpoint_info: EndpointInfo
    request_type: type[BaseModel] | None
    response_type: type[BaseModel] | None
    error_map: dict[int, type[DomainError]] = field(default_factory=dict)
    path_params: set[str] = field(init=False)

    def __post_init__(self) -> None:
        self.path_params = extract_path_params(self.endpoint_info.path)

    def __get__(self, obj: ClientT | None, objtype: type) -> Any:
        if obj is None:
            return self
        return self._create_bound_endpoint(obj)

    def _create_bound_endpoint(self, client: ClientT) -> Any:
        """Create a bound endpoint for the given client. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _create_bound_endpoint")


# ---------------------------------------------------------------------------
# Base Bound Endpoint
# ---------------------------------------------------------------------------

# from abc import ABC, abstractmethod


# class ParseStrategy[T](ABC):
#     def __init__(self, response_type: type[T]) -> None:
#         self.response_type: type[T] = response_type

#     @abstractmethod
#     def parse(self, response: HttpResponse) -> T:
#         raise NotImplementedError

# class ParsePydanticModel[T: BaseModel](ParseStrategy[T]):
#     def parse(self, response: HttpResponse) -> T:
#         data = response.content
#         return self.response_type.model_validate(data)


@dataclass
class BaseBoundEndpoint[ClientT: BaseAPIClient[Any]]:
    """
    Base class for bound endpoints with shared preparation logic.

    Subclasses implement __call__ (sync) or __call__ as async.
    """

    client: ClientT
    endpoint_info: EndpointInfo
    response_type: type[BaseModel] | None
    path_params: set[str]
    error_map: dict[int, type[DomainError]] = field(default_factory=dict)
    # parse_strategy: ParseStrategy

    def _prepare(self, request: BaseModel | None) -> PreparedRequest:
        """Build a PreparedRequest from the endpoint info and request data."""
        return prepare_request(
            request=request,
            endpoint_info=self.endpoint_info,
            path_params=self.path_params,
            base_url=self.client._base_url,
            default_headers=self.client._default_headers,
            model_dump_mode=self.client._model_dump_mode,
        )

    def _resolve_domain_error(self, error: HttpError) -> DomainError | None:
        """Resolve a declarative domain error for this status code, if any.

        Per-endpoint ``Raises`` mappings take precedence over the client-wide
        ``errors`` mapping. Returns ``None`` when nothing matches, leaving the
        error to ``handle_error``.
        """
        exc_type = self.error_map.get(error.status_code) or self.client.errors.get(error.status_code)
        if exc_type is None:
            return None
        return exc_type.from_http_error(error)

    def _handle_response(self, response: HttpResponse) -> BaseModel | dict[str, Any] | list[Any] | None:
        """Handle response: translate/raise on error, parse on success."""
        if response.status_code >= 400:
            error = HttpError(response.status_code, response.content, dict(response.headers), self.endpoint_info)
            # 1. Declarative mapping (per-endpoint Raises, then client errors map).
            domain_error = self._resolve_domain_error(error)
            if domain_error is not None:
                raise domain_error
            # 2. Fallback / full-control hook. Default raises the HttpError.
            self.client.handle_error(error)
            # handle_error is expected to raise; if it returns, suppress the error.
            return None
        return parse_response(response, self.endpoint_info, self.response_type)
