"""
Core types for endpoint definitions.

This module contains the fundamental types used to describe endpoints:
- RequestStyle: How to serialize request data
- ResponseStyle: How to deserialize response data
- EndpointInfo: Metadata bundle stored in Annotated types
- ExtractedEndpoint: Result of extracting endpoint info from a type hint
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from http import HTTPMethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


class RequestStyle(Enum):
    """How to serialize request data for the HTTP call."""

    QUERY = auto()  # Serialize to query string (GET, DELETE)
    BODY = auto()  # Serialize to JSON body (POST, PUT, PATCH)


class ResponseStyle(Enum):
    """How to deserialize response data."""

    JSON = auto()  # Parse as JSON into Pydantic model (default)
    TEXT = auto()  # Return as string
    BYTES = auto()  # Return raw bytes
    NONE = auto()  # No response body expected (204 No Content, etc.)


@dataclass(frozen=True)
class EndpointInfo:
    """Metadata about an endpoint, stored in Annotated type."""

    method: HTTPMethod
    path: str
    request_style: RequestStyle
    response_style: ResponseStyle


@dataclass(frozen=True)
class ExtractedEndpoint:
    """Result of extracting endpoint info from a type hint."""

    request_type: type[BaseModel] | None
    response_type: type[BaseModel] | None
    info: EndpointInfo
