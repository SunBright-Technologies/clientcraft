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
from dataclasses import dataclass, field
from typing import Any, get_type_hints
from urllib.parse import urlencode

from pydantic import BaseModel

from ._endpoints import extract_endpoint_info
from ._responses import BytesResponse, TextResponse
from ._types import EndpointInfo, RequestStyle, ResponseStyle
from .backends import HttpResponse

# ---------------------------------------------------------------------------
# HTTP Error
# ---------------------------------------------------------------------------


class HttpError(Exception):
    """HTTP error with status code and response content."""

    def __init__(self, status_code: int, content: bytes, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        super().__init__(f"HTTP {status_code}: {content.decode('utf-8', errors='replace')}")


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
    request: BaseModel,
    endpoint_info: EndpointInfo,
    path_params: set[str],
    base_url: str,
    default_headers: dict[str, str],
) -> PreparedRequest:
    """Build a PreparedRequest from the endpoint info and request data."""
    request_dict = request.model_dump(exclude_none=True)

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
                )
                setattr(cls, name, descriptor)

    def __init__(
        self,
        base_url: str,
        backend: Backend,
        *,
        default_headers: dict[str, str] | None = None,
        default_timeout: float | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._backend = backend
        self._default_headers = default_headers or {}
        self._default_timeout = default_timeout


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
    # parse_strategy: ParseStrategy

    def _prepare(self, request: BaseModel) -> PreparedRequest:
        """Build a PreparedRequest from the endpoint info and request data."""
        return prepare_request(
            request=request,
            endpoint_info=self.endpoint_info,
            path_params=self.path_params,
            base_url=self.client._base_url,
            default_headers=self.client._default_headers,
        )

    def _handle_response(self, response: HttpResponse) -> BaseModel | dict[str, Any] | list[Any] | None:
        """Handle response: raise on error, parse on success."""
        if response.status_code >= 400:
            raise HttpError(response.status_code, response.content, dict(response.headers))
        return parse_response(response, self.endpoint_info, self.response_type)
