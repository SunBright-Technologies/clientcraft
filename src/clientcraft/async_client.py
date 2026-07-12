"""
Asynchronous API Client.

Usage:
    from clientcraft import AsyncGet, AsyncPost, AsyncDelete
    from clientcraft.async_client import AsyncAPIClient
    from clientcraft.backends import AsyncHttpBackend, AiohttpBackend

    class UserAPI(AsyncAPIClient):
        get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]
        create_user: AsyncPost[CreateUserRequest, User, Literal["/users"]]
        delete_user: AsyncDelete[DeleteUserRequest, None, Literal["/users/{user_id}"]]

    async with AiohttpBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = await client.get_user(GetUserRequest(user_id="123"))
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
from .backends import AsyncHttpBackend, HttpResponse

__all__ = [
    "AsyncAPIClient",
    "AsyncHttpBackend",
    "DomainError",
    "ErrorMap",
    "HttpError",
    "HttpResponse",
    "PreparedRequest",
]


@dataclass
class _AsyncBoundEndpoint(BaseBoundEndpoint["AsyncAPIClient"]):
    """An awaitable endpoint bound to an async client instance."""

    async def __call__(self, request: BaseModel | None = None) -> BaseModel | dict[str, Any] | list[Any] | None:
        """Execute the endpoint call asynchronously.

        ``request`` may be ``None`` for endpoints declared with a ``None`` request
        type (i.e. endpoints that take no parameters at all).
        """
        prepared = self._prepare(request)

        response = await self.client._backend.request(
            method=prepared.method,
            url=prepared.url,
            content=prepared.content,
            headers=prepared.headers,
            timeout=self.client._default_timeout,
        )

        return self._handle_response(response)


@dataclass
class _AsyncEndpointDescriptor(EndpointDescriptor["AsyncAPIClient"]):
    """Descriptor that creates async bound endpoints."""

    def _create_bound_endpoint(self, client: AsyncAPIClient) -> _AsyncBoundEndpoint:
        return _AsyncBoundEndpoint(
            client=client,
            endpoint_info=self.endpoint_info,
            response_type=self.response_type,
            path_params=self.path_params,
            error_map=self.error_map,
        )


class AsyncAPIClient(BaseAPIClient[AsyncHttpBackend]):
    """
    Base class for declarative asynchronous API clients.

    Subclass this and declare endpoints using type annotations:

        class UserAPI(AsyncAPIClient):
            get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]
            create_user: AsyncPost[CreateUserRequest, User, Literal["/users"]]
            delete_user: AsyncDelete[DeleteUserRequest, None, Literal["/users/{user_id}"]]

        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = await client.get_user(GetUserRequest(user_id="123"))
    """

    _descriptor_factory = _AsyncEndpointDescriptor
