"""Tests for customizable error handling and declarative domain-error mapping."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Literal

import pytest

from clientcraft import DEFAULT, AsyncGet, DomainError, ErrorMap, Get, HttpError, Raises
from clientcraft.async_client import AsyncAPIClient
from clientcraft.client import APIClient

from .conftest import AsyncMockBackend, GetUserRequest, MockBackend, SearchRequest, User, UserAPI

# ---------------------------------------------------------------------------
# handle_error hook
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test the customizable error handling hook."""

    def test_default_handle_error_raises_http_error(self, mock_backend: MockBackend) -> None:
        """Default handle_error raises HttpError on status >= 400."""
        mock_backend.response_status = 404
        mock_backend.response_content = b'{"detail": "not found"}'

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(HttpError) as exc_info:
            client.get_user(GetUserRequest(user_id="123"))

        assert exc_info.value.status_code == 404
        assert exc_info.value.content == b'{"detail": "not found"}'

    def test_override_translates_to_domain_error(self, mock_backend: MockBackend) -> None:
        """Overriding handle_error lets users raise domain-specific exceptions."""

        class UserNotFound(Exception):
            def __init__(self, path: str) -> None:
                self.path = path

        class CustomAPI(UserAPI):
            def handle_error(self, error: HttpError) -> None:
                if error.status_code == 404:
                    assert error.endpoint_info is not None
                    raise UserNotFound(error.endpoint_info.path) from error
                super().handle_error(error)

        mock_backend.response_status = 404
        client = CustomAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(UserNotFound) as exc_info:
            client.get_user(GetUserRequest(user_id="123"))

        assert exc_info.value.path == "/users/{user_id}"

    def test_override_falls_back_to_super(self, mock_backend: MockBackend) -> None:
        """Non-matching status codes fall through to the default HttpError."""

        class CustomAPI(UserAPI):
            def handle_error(self, error: HttpError) -> None:
                if error.status_code == 404:
                    raise ValueError("handled")
                super().handle_error(error)

        mock_backend.response_status = 500
        client = CustomAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(HttpError):
            client.get_user(GetUserRequest(user_id="123"))


# ---------------------------------------------------------------------------
# Declarative domain-error mapping
# ---------------------------------------------------------------------------


class UserNotFoundError(DomainError):
    """404 -> domain error, default construction."""


class RateLimitedError(DomainError):
    """429 -> domain error."""


class ValidationFailed(DomainError):
    """422 -> domain error that parses the response body."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    @classmethod
    def from_http_error(cls, error: HttpError) -> DomainError:
        payload = json.loads(error.content)
        exc = cls(payload["message"])
        exc.http_error = error
        return exc


class MappedUserAPI(APIClient):
    """Per-endpoint Raises plus a client-wide errors map."""

    get_user: Annotated[
        Get[GetUserRequest, User, Literal["/users/{user_id}"]],
        Raises(404, UserNotFoundError),
        Raises(422, ValidationFailed),
    ]
    search_users: Get[SearchRequest, User, Literal["/users/search"]]

    errors = ErrorMap({429: RateLimitedError, 404: RateLimitedError})


class ApiError(DomainError):
    """Catch-all domain error."""


class CatchAllAPI(APIClient):
    """Exercises DEFAULT catch-all, per-endpoint and client-wide."""

    # per-endpoint: 404 exact, everything else -> ApiError
    get_user: Annotated[
        Get[GetUserRequest, User, Literal["/users/{user_id}"]],
        Raises(404, UserNotFoundError),
        Raises(DEFAULT, ApiError),
    ]
    # no per-endpoint mapping: falls to the client-wide catch-all
    search_users: Get[SearchRequest, User, Literal["/users/search"]]

    errors = ErrorMap({429: RateLimitedError, DEFAULT: ApiError})


class TestDomainErrorMapping:
    """Declarative status -> DomainError translation."""

    def test_per_endpoint_mapping(self, mock_backend: MockBackend) -> None:
        mock_backend.response_status = 404
        mock_backend.response_content = b'{"detail": "nope"}'
        client = MappedUserAPI(base_url="https://api.example.com", backend=mock_backend)

        with pytest.raises(UserNotFoundError) as exc_info:
            client.get_user(GetUserRequest(user_id="x"))

        # carries the original HttpError
        assert exc_info.value.http_error is not None
        assert exc_info.value.http_error.status_code == 404
        assert exc_info.value.http_error.endpoint_info is not None
        assert exc_info.value.http_error.endpoint_info.path == "/users/{user_id}"

    def test_from_http_error_parses_body(self, mock_backend: MockBackend) -> None:
        mock_backend.response_status = 422
        mock_backend.response_content = b'{"message": "bad email"}'
        client = MappedUserAPI(base_url="https://api.example.com", backend=mock_backend)

        with pytest.raises(ValidationFailed) as exc_info:
            client.get_user(GetUserRequest(user_id="x"))
        assert exc_info.value.message == "bad email"

    def test_per_endpoint_beats_client_map(self, mock_backend: MockBackend) -> None:
        # 404 is in both maps; the per-endpoint Raises wins.
        mock_backend.response_status = 404
        client = MappedUserAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(UserNotFoundError):
            client.get_user(GetUserRequest(user_id="x"))

    def test_client_map_applies_without_per_endpoint(self, mock_backend: MockBackend) -> None:
        # search_users has no Raises; 429 resolves via the client errors map.
        mock_backend.response_status = 429
        client = MappedUserAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(RateLimitedError):
            client.search_users(SearchRequest(query="x"))

    def test_unmapped_status_falls_back_to_http_error(self, mock_backend: MockBackend) -> None:
        mock_backend.response_status = 500
        client = MappedUserAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(HttpError):
            client.get_user(GetUserRequest(user_id="x"))

    def test_no_mapping_is_backward_compatible(self, mock_backend: MockBackend) -> None:
        # A plain client with no errors map / no Raises behaves exactly as before.
        mock_backend.response_status = 404
        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(HttpError):
            client.get_user(GetUserRequest(user_id="x"))

    def test_duplicate_raises_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="Conflicting Raises for status 404"):

            class BadAPI(APIClient):
                get_user: Annotated[
                    Get[GetUserRequest, User, Literal["/users/{user_id}"]],
                    Raises(404, UserNotFoundError),
                    Raises(404, RateLimitedError),
                ]

    # --- catch-all (DEFAULT) ------------------------------------------------

    def test_per_endpoint_default_catches_unmapped(self, mock_backend: MockBackend) -> None:
        # 500 has no exact mapping on the endpoint -> per-endpoint DEFAULT.
        mock_backend.response_status = 500
        client = CatchAllAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(ApiError):
            client.get_user(GetUserRequest(user_id="x"))

    def test_exact_status_beats_default(self, mock_backend: MockBackend) -> None:
        # 404 has an exact mapping, so it wins over the DEFAULT catch-all.
        mock_backend.response_status = 404
        client = CatchAllAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(UserNotFoundError):
            client.get_user(GetUserRequest(user_id="x"))

    def test_client_default_catches_when_no_per_endpoint(self, mock_backend: MockBackend) -> None:
        # search_users has no Raises; 500 resolves via the client-wide DEFAULT.
        mock_backend.response_status = 500
        client = CatchAllAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(ApiError):
            client.search_users(SearchRequest(query="x"))

    def test_client_exact_beats_client_default(self, mock_backend: MockBackend) -> None:
        # 429 has an exact client mapping; it wins over the client DEFAULT.
        mock_backend.response_status = 429
        client = CatchAllAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(RateLimitedError):
            client.search_users(SearchRequest(query="x"))


# ---------------------------------------------------------------------------
# Async: both hooks route through the same machinery
# ---------------------------------------------------------------------------


class AsyncUserAPI(AsyncAPIClient):
    get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]


class AsyncUserNotFound(DomainError):
    pass


class AsyncMappedAPI(AsyncAPIClient):
    get_user: Annotated[
        AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]],
        Raises(404, AsyncUserNotFound),
    ]


class TestAsyncErrorHandling:
    def test_async_handle_error_override(self) -> None:
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

        with pytest.raises(UserNotFound):
            asyncio.run(do_call())

    def test_async_declarative_mapping(self) -> None:
        backend = AsyncMockBackend()
        backend.response_status = 404
        client = AsyncMappedAPI(base_url="https://api.example.com", backend=backend)

        async def do_call() -> None:
            await client.get_user(GetUserRequest(user_id="123"))

        with pytest.raises(AsyncUserNotFound) as exc_info:
            asyncio.run(do_call())
        assert exc_info.value.http_error is not None
        assert exc_info.value.http_error.status_code == 404
