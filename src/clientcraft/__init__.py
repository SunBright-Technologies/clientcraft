from __future__ import annotations

from importlib.metadata import version

# Base utilities (useful for custom backends or extensions)
from ._base import DomainError, ErrorMap, HttpError, PreparedRequest, prepare_request

# Endpoint types (sync)
# Endpoint types (async) - same runtime behavior, different type stubs
# Extraction utility
from ._endpoints import (
    AsyncDelete,
    AsyncGet,
    AsyncPatch,
    AsyncPost,
    AsyncPut,
    Delete,
    Get,
    Patch,
    Post,
    Put,
    extract_endpoint_info,
)

# Response wrappers
from ._responses import BytesResponse, TextResponse

# Core types
from ._types import DEFAULT, EndpointInfo, ExtractedEndpoint, Raises, RequestStyle, ResponseStyle

# Clients
from .async_client import AsyncAPIClient

# Backend protocols (for type annotations)
from .backends import AsyncHttpBackend, HttpBackend, HttpResponse
from .client import APIClient

__version__ = version("clientcraft")

__all__ = [
    # Version
    "__version__",
    # Core types
    "EndpointInfo",
    "ExtractedEndpoint",
    "RequestStyle",
    "ResponseStyle",
    # Response wrappers
    "BytesResponse",
    "TextResponse",
    # Sync endpoint types
    "Delete",
    "Get",
    "Patch",
    "Post",
    "Put",
    # Async endpoint types
    "AsyncDelete",
    "AsyncGet",
    "AsyncPatch",
    "AsyncPost",
    "AsyncPut",
    # Utilities
    "extract_endpoint_info",
    "prepare_request",
    # Errors
    "DEFAULT",
    "DomainError",
    "ErrorMap",
    "HttpError",
    "Raises",
    "PreparedRequest",
    # Clients
    "APIClient",
    "AsyncAPIClient",
    # Backend protocols
    "HttpBackend",
    "AsyncHttpBackend",
    "HttpResponse",
]
