"""
Synchronous API Client.

Usage:
    from clientcraft import Get, Post, Delete
    from clientcraft.client import APIClient
    from clientcraft.backends import HttpBackend

    class UserAPI(APIClient):
        get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
        create_user: Post[CreateUserRequest, User, Literal["/users"]]
        delete_user: Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]

    client = UserAPI(base_url="https://api.example.com", backend=my_backend)
    user = client.get_user(GetUserRequest(user_id="123"))
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ._base import (
    BaseAPIClient,
    BaseBoundEndpoint,
    DomainError,
    EndpointDescriptor,
    ErrorMap,
    HttpError,
    PreparedRequest,
)
from .backends import HttpBackend, HttpResponse

__all__ = [
    "APIClient",
    "DomainError",
    "ErrorMap",
    "HttpBackend",
    "HttpError",
    "HttpResponse",
    "PreparedRequest",
]


@dataclass
class _BoundEndpoint(BaseBoundEndpoint["APIClient"]):
    """A callable endpoint bound to a sync client instance."""

    def __call__(self, request: BaseModel | None = None) -> BaseModel | dict[str, Any] | list[Any] | None:
        """Execute the endpoint call synchronously.

        ``request`` may be ``None`` for endpoints declared with a ``None`` request
        type (i.e. endpoints that take no parameters at all).
        """
        prepared = self._prepare(request)

        response = self.client._backend.request(
            method=prepared.method,
            url=prepared.url,
            content=prepared.content,
            headers=prepared.headers,
            timeout=self.client._default_timeout,
        )

        return self._handle_response(response)


@dataclass
class _SyncEndpointDescriptor(EndpointDescriptor["APIClient"]):
    """Descriptor that creates sync bound endpoints."""

    def _create_bound_endpoint(self, client: APIClient) -> _BoundEndpoint:
        return _BoundEndpoint(
            client=client,
            endpoint_info=self.endpoint_info,
            response_type=self.response_type,
            path_params=self.path_params,
            error_map=self.error_map,
        )


class APIClient(BaseAPIClient[HttpBackend]):
    """
    Base class for declarative synchronous API clients.

    Subclass this and declare endpoints using type annotations:

        class UserAPI(APIClient):
            get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
            create_user: Post[CreateUserRequest, User, Literal["/users"]]
            delete_user: Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]

        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = client.get_user(GetUserRequest(user_id="123"))
    """

    _descriptor_factory = _SyncEndpointDescriptor
