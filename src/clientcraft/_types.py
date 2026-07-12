"""
Core types for endpoint definitions.

This module contains the fundamental types used to describe endpoints:
- RequestStyle: How to serialize request data
- ResponseStyle: How to deserialize response data
- EndpointInfo: Metadata bundle stored in Annotated types
- ExtractedEndpoint: Result of extracting endpoint info from a type hint
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from http import HTTPMethod
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pydantic import BaseModel

    from ._base import DomainError

# How request models are serialized via ``BaseModel.model_dump``.
# - "json" (client default): coerce values to JSON-compatible types (e.g. datetime -> str)
# - "python": keep Python-native types (the pydantic default)
type ModelDumpMode = Literal["python", "json"]


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
class Raises:
    """Declarative per-endpoint error mapping.

    Attached as ``Annotated`` metadata alongside an endpoint declaration to map a
    status code to a :class:`~clientcraft.DomainError` subclass::

        get_user: Annotated[
            Get[GetUserRequest, User, Literal["/users/{user_id}"]],
            Raises(404, UserNotFound),
        ]

    Multiple ``Raises(...)`` items may be listed; each maps one status code.
    Python flattens the nested ``Annotated``, so they are collected together.
    """

    status: int
    exc: type[DomainError]


@dataclass(frozen=True)
class ExtractedEndpoint:
    """Result of extracting endpoint info from a type hint."""

    request_type: type[BaseModel] | None
    response_type: type[BaseModel] | None
    info: EndpointInfo
    error_map: dict[int, type[DomainError]] = field(default_factory=dict)
