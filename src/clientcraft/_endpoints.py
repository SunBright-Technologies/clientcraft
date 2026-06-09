"""
Endpoint type construction.

This module defines the endpoint types (Get, Post, Put, Patch, Delete) and their
async variants (AsyncGet, AsyncPost, etc.) using a metaclass to transform
`Get[Request, Response, Literal["/path"]]` into an Annotated type with EndpointInfo.

The type stubs (.pyi files) tell type checkers what the return types are:
- Sync types (Get, Post, etc.) return TResponse directly
- Async types (AsyncGet, AsyncPost, etc.) return Coroutine[Any, Any, TResponse]
"""

from __future__ import annotations

from http import HTTPMethod
from typing import Annotated, Any, Literal, get_args, get_origin

from pydantic import BaseModel

from ._responses import BytesResponse, TextResponse
from ._types import EndpointInfo, ExtractedEndpoint, RequestStyle, ResponseStyle


def _get_response_style(response_type: type | None) -> ResponseStyle:
    """Determine response style based on response type."""
    if response_type is None or response_type is type(None):
        return ResponseStyle.NONE
    if response_type is TextResponse:
        return ResponseStyle.TEXT
    if response_type is BytesResponse:
        return ResponseStyle.BYTES
    return ResponseStyle.JSON


def _extract_literal(t: Any) -> str | None:
    """Extract string value from a Literal type."""
    if get_origin(t) is Literal:
        args = get_args(t)
        if args and isinstance(args[0], str):
            return args[0]
    return None


# ---------------------------------------------------------------------------
# Marker type for endpoints
# ---------------------------------------------------------------------------


class Endpoint[TRequest: BaseModel, TResponse: BaseModel]:
    """
    Marker type for endpoints.

    This class is never instantiated - it only exists to carry type parameters.
    The actual callable behavior comes from the descriptor created by APIClient.
    """

    def __call__(self, request: TRequest) -> TResponse:
        """Type signature for the endpoint call."""
        raise NotImplementedError("Endpoint should be used via APIClient")


# ---------------------------------------------------------------------------
# Metaclass for endpoint type construction
# ---------------------------------------------------------------------------


class _EndpointTypeMeta(type):
    """Metaclass that makes Get[Req, Resp, Literal["/path"]] return an Annotated type."""

    _method: HTTPMethod
    _request_style: RequestStyle

    def __getitem__(cls, params: tuple[type, type, Any]) -> Any:
        if not isinstance(params, tuple) or len(params) != 3:
            raise TypeError(f"{cls.__name__} requires 3 type parameters: [Request, Response, Path]")

        request_type, response_type, path_type = params

        # Extract path from Literal
        path = _extract_literal(path_type)
        if path is None and isinstance(path_type, str):
            path = path_type

        if path is None:
            raise TypeError(f"Path must be a Literal string, got {path_type}")

        # Determine response style from response type
        response_style = _get_response_style(response_type)

        # Return Annotated type with endpoint info
        # Type checkers can't understand runtime type construction - we use .pyi stubs instead
        return Annotated[
            Endpoint[request_type, response_type],  # type: ignore[valid-type]
            EndpointInfo(
                method=cls._method,
                path=path,
                request_style=cls._request_style,
                response_style=response_style,
            ),
        ]


# ---------------------------------------------------------------------------
# Sync endpoint types
# ---------------------------------------------------------------------------


class Get(metaclass=_EndpointTypeMeta):
    """GET endpoint type - sends data as query parameters."""

    _method = HTTPMethod.GET
    _request_style = RequestStyle.QUERY


class Post(metaclass=_EndpointTypeMeta):
    """POST endpoint type - sends data as JSON body."""

    _method = HTTPMethod.POST
    _request_style = RequestStyle.BODY


class Put(metaclass=_EndpointTypeMeta):
    """PUT endpoint type - sends data as JSON body."""

    _method = HTTPMethod.PUT
    _request_style = RequestStyle.BODY


class Patch(metaclass=_EndpointTypeMeta):
    """PATCH endpoint type - sends data as JSON body."""

    _method = HTTPMethod.PATCH
    _request_style = RequestStyle.BODY


class Delete(metaclass=_EndpointTypeMeta):
    """DELETE endpoint type - sends data as query parameters."""

    _method = HTTPMethod.DELETE
    _request_style = RequestStyle.QUERY


# ---------------------------------------------------------------------------
# Async endpoint types
#
# At runtime, these behave identically to the sync versions.
# The type stubs (.pyi) tell type checkers that these return Coroutine.
# ---------------------------------------------------------------------------

AsyncGet = Get
AsyncPost = Post
AsyncPut = Put
AsyncPatch = Patch
AsyncDelete = Delete


# ---------------------------------------------------------------------------
# Extraction utility
# ---------------------------------------------------------------------------


def extract_endpoint_info(hint: Any) -> ExtractedEndpoint | None:
    """
    Extract endpoint info from an Annotated type hint.

    Returns ExtractedEndpoint if the hint is a valid endpoint type, None otherwise.
    """
    if get_origin(hint) is not Annotated:
        return None

    args = get_args(hint)
    if len(args) < 2:
        return None

    base_type, *annotations = args
    base_args = get_args(base_type)

    if len(base_args) < 2:
        return None

    request_type, response_type = base_args[0], base_args[1]

    if not isinstance(request_type, type) or not isinstance(response_type, type):
        return None

    endpoint_info = next((a for a in annotations if isinstance(a, EndpointInfo)), None)
    if endpoint_info is None:
        return None

    return ExtractedEndpoint(
        request_type=request_type,
        response_type=response_type,
        info=endpoint_info,
    )
