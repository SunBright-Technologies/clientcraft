"""Tests for async client support."""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel

from clientcraft import AsyncDelete, AsyncGet, AsyncPost
from clientcraft.async_client import AsyncAPIClient

from .conftest import (
    AsyncMockBackend,
    DeleteUserRequest,
    GetUserRequest,
    User,
)

# ---------------------------------------------------------------------------
# Test-specific async API clients (must be at module level for get_type_hints)
# ---------------------------------------------------------------------------


class AsyncUserAPI(AsyncAPIClient):
    get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]


class AsyncUserDeleteAPI(AsyncAPIClient):
    delete_user: AsyncDelete[DeleteUserRequest, None, Literal["/users/{user_id}"]]


class AsyncCreateUserRequest(BaseModel):
    name: str
    email: str


class AsyncUserCreateAPI(AsyncAPIClient):
    create_user: AsyncPost[AsyncCreateUserRequest, User, Literal["/users"]]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAsyncSupport:
    """Test async HTTP backend support."""

    def test_async_client_works(self) -> None:
        """Async client should work with async backend."""
        async_backend = AsyncMockBackend()
        async_backend.response_content = b'{"id": "123", "name": "Async User", "email": "async@example.com"}'

        client = AsyncUserAPI(base_url="https://api.example.com", backend=async_backend)

        async def do_async_call() -> User | None:
            return await client.get_user(GetUserRequest(user_id="123"))

        result = asyncio.run(do_async_call())

        assert async_backend.last_request is not None
        assert async_backend.last_request.method == "GET"
        assert async_backend.last_request.url == "https://api.example.com/users/123"
        assert result is not None
        assert result.name == "Async User"
        assert isinstance(result, User)

    def test_async_delete_returns_none(self) -> None:
        """Async delete with None response should return None."""
        async_backend = AsyncMockBackend()
        async_backend.response_status = 204
        async_backend.response_content = b""

        client = AsyncUserDeleteAPI(base_url="https://api.example.com", backend=async_backend)

        async def do_delete() -> None:
            return await client.delete_user(DeleteUserRequest(user_id="123"))

        result = asyncio.run(do_delete())
        assert result is None

    def test_async_post_sends_body(self) -> None:
        """Async POST should send JSON body."""
        async_backend = AsyncMockBackend()
        async_backend.response_content = b'{"id": "456", "name": "New User", "email": "new@example.com"}'

        client = AsyncUserCreateAPI(base_url="https://api.example.com", backend=async_backend)

        async def do_create() -> User | None:
            return await client.create_user(AsyncCreateUserRequest(name="New User", email="new@example.com"))

        result = asyncio.run(do_create())

        assert async_backend.last_request is not None
        assert async_backend.last_request.method == "POST"
        assert async_backend.last_request.content is not None
        assert b'"name": "New User"' in async_backend.last_request.content
        assert result is not None
        assert result.name == "New User"


def test_async_handle_error_override() -> None:
    """The async client routes error responses through handle_error too."""
    from clientcraft.async_client import HttpError

    class UserNotFound(Exception):
        pass

    class CustomAsyncAPI(AsyncUserAPI):
        def handle_error(self, error: HttpError) -> None:
            if error.status_code == 404:
                raise UserNotFound from error
            super().handle_error(error)

    backend = AsyncMockBackend()
    backend.response_status = 404
    client = CustomAsyncAPI(base_url="https://api.example.com", backend=backend)

    async def do_call() -> None:
        await client.get_user(GetUserRequest(user_id="123"))

    import pytest

    with pytest.raises(UserNotFound):
        asyncio.run(do_call())


# ---------------------------------------------------------------------------
# Declarative domain-error mapping (async)
# ---------------------------------------------------------------------------

from typing import Annotated  # noqa: E402

from clientcraft import DomainError, Raises  # noqa: E402


class AsyncUserNotFound(DomainError):
    pass


class AsyncMappedAPI(AsyncUserAPI):
    get_user: Annotated[
        AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]],
        Raises(404, AsyncUserNotFound),
    ]


def test_async_declarative_mapping() -> None:
    import pytest

    backend = AsyncMockBackend()
    backend.response_status = 404
    client = AsyncMappedAPI(base_url="https://api.example.com", backend=backend)

    async def do_call() -> None:
        await client.get_user(GetUserRequest(user_id="123"))

    with pytest.raises(AsyncUserNotFound) as exc_info:
        asyncio.run(do_call())
    assert exc_info.value.http_error is not None
    assert exc_info.value.http_error.status_code == 404
