"""Tests for endpoints that take no parameters (``None`` request type).

These endpoints are declared as ``Get[None, Response, Path]`` (and async/other
method variants). They may be called with no argument or with an explicit
``None`` and send neither query params nor a body.
"""

from __future__ import annotations

import asyncio
from typing import Literal, get_type_hints

from clientcraft import AsyncGet, Get, extract_endpoint_info
from clientcraft.async_client import AsyncAPIClient
from clientcraft.client import APIClient

from .conftest import AsyncMockBackend, MockBackend, User, UserList

# ---------------------------------------------------------------------------
# Test-specific API clients (must be at module level for get_type_hints)
# ---------------------------------------------------------------------------


class HealthAPI(APIClient):
    list_users: Get[None, UserList, Literal["/users"]]


class AsyncHealthAPI(AsyncAPIClient):
    list_users: AsyncGet[None, UserList, Literal["/users"]]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoParamEndpoint:
    """Endpoints declared with a ``None`` request type take no parameters."""

    def test_endpoint_is_registered(self) -> None:
        """A None request type should still be extracted and registered."""
        hints = get_type_hints(HealthAPI, include_extras=True)
        extracted = extract_endpoint_info(hints["list_users"])
        assert extracted is not None
        assert extracted.request_type is type(None)

    def test_call_with_no_argument(self, mock_backend: MockBackend) -> None:
        """Calling with no argument sends no body and no query string."""
        mock_backend.response_content = b'{"users": []}'

        client = HealthAPI(base_url="https://api.example.com", backend=mock_backend)
        result = client.list_users()

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.method == "GET"
        assert mock_backend.last_request.url == "https://api.example.com/users"
        assert mock_backend.last_request.content is None
        assert isinstance(result, UserList)

    def test_call_with_explicit_none(self, mock_backend: MockBackend) -> None:
        """Calling with an explicit None behaves the same as no argument."""
        mock_backend.response_content = b'{"users": [{"id": "1", "name": "A", "email": "a@e.com"}]}'

        client = HealthAPI(base_url="https://api.example.com", backend=mock_backend)
        result = client.list_users(None)

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.url == "https://api.example.com/users"
        assert mock_backend.last_request.content is None
        assert isinstance(result, UserList)
        assert result.users[0] == User(id="1", name="A", email="a@e.com")

    def test_async_call_with_no_argument(self) -> None:
        """Async no-param endpoint should work when awaited with no argument."""
        async_backend = AsyncMockBackend()
        async_backend.response_content = b'{"users": []}'

        client = AsyncHealthAPI(base_url="https://api.example.com", backend=async_backend)

        async def do_call() -> UserList | None:
            return await client.list_users()

        result = asyncio.run(do_call())

        assert async_backend.last_request is not None
        assert async_backend.last_request.url == "https://api.example.com/users"
        assert async_backend.last_request.content is None
        assert isinstance(result, UserList)
