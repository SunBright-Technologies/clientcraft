"""Tests for HttpxBackend and HttpxAsyncBackend implementations."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from clientcraft.backends.httpx import HttpxAsyncBackend, HttpxBackend, HttpxResponse

from .conftest import AsyncBackendInterfaceTests, BackendInterfaceTests, MockResponseData

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator


# -----------------------------------------------------------------------------
# Sync Backend Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def backend() -> Iterator[HttpxBackend]:
    """Create a HttpxBackend within context manager."""
    with HttpxBackend() as b:
        yield b


@pytest.fixture
def mock_request(backend: HttpxBackend) -> Callable[[MockResponseData], Any]:
    """Create a mock request context manager for the sync backend."""

    @contextmanager
    def _mock(data: MockResponseData) -> Iterator[MagicMock]:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = data.status_code
        mock_response.content = data.content
        mock_response.headers = httpx.Headers(data.headers or {})

        with patch.object(backend._client, "request", return_value=mock_response) as mock:
            yield mock

    return _mock


# -----------------------------------------------------------------------------
# Async Backend Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
async def async_backend() -> AsyncIterator[HttpxAsyncBackend]:
    """Create a HttpxAsyncBackend within async context manager."""
    async with HttpxAsyncBackend() as b:
        yield b


@pytest.fixture
def mock_async_request(async_backend: HttpxAsyncBackend) -> Callable[[MockResponseData], Any]:
    """Create a mock request context manager for the async backend."""

    @contextmanager
    def _mock(data: MockResponseData) -> Iterator[AsyncMock]:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = data.status_code
        mock_response.content = data.content
        mock_response.headers = httpx.Headers(data.headers or {})

        with patch.object(
            async_backend._client, "request", new_callable=AsyncMock, return_value=mock_response
        ) as mock:
            yield mock

    return _mock


# -----------------------------------------------------------------------------
# Sync Interface Tests
# -----------------------------------------------------------------------------


class TestHttpxBackendInterface(BackendInterfaceTests[HttpxBackend]):
    """Test that HttpxBackend conforms to the HttpBackend interface."""

    @pytest.fixture
    def backend(self) -> Iterator[HttpxBackend]:
        """Provide a HttpxBackend instance."""
        with HttpxBackend() as b:
            yield b

    @pytest.fixture
    def mock_request(self, backend: HttpxBackend) -> Callable[[MockResponseData], Any]:
        """Provide mock request function for HttpxBackend."""

        @contextmanager
        def _mock(data: MockResponseData) -> Iterator[MagicMock]:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = data.status_code
            mock_response.content = data.content
            mock_response.headers = httpx.Headers(data.headers or {})

            with patch.object(backend._client, "request", return_value=mock_response) as mock:
                yield mock

        return _mock


# -----------------------------------------------------------------------------
# Async Interface Tests
# -----------------------------------------------------------------------------


class TestHttpxAsyncBackendInterface(AsyncBackendInterfaceTests[HttpxAsyncBackend]):
    """Test that HttpxAsyncBackend conforms to the AsyncHttpBackend interface."""

    @pytest.fixture
    async def async_backend(self) -> AsyncIterator[HttpxAsyncBackend]:
        """Provide a HttpxAsyncBackend instance."""
        async with HttpxAsyncBackend() as b:
            yield b

    @pytest.fixture
    def mock_async_request(
        self, async_backend: HttpxAsyncBackend
    ) -> Callable[[MockResponseData], Any]:
        """Provide mock request function for HttpxAsyncBackend."""

        @contextmanager
        def _mock(data: MockResponseData) -> Iterator[AsyncMock]:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = data.status_code
            mock_response.content = data.content
            mock_response.headers = httpx.Headers(data.headers or {})

            with patch.object(
                async_backend._client, "request", new_callable=AsyncMock, return_value=mock_response
            ) as mock:
                yield mock

        return _mock


# -----------------------------------------------------------------------------
# Sync Lifecycle Tests
# -----------------------------------------------------------------------------


class TestHttpxBackendLifecycle:
    """Test HttpxBackend lifecycle management."""

    def test_requires_context_manager_or_client(self) -> None:
        """Should raise error if used without client."""
        backend = HttpxBackend()

        with pytest.raises(RuntimeError, match="requires a client"):
            backend.request("GET", "https://example.com")

    def test_context_manager_creates_client(self) -> None:
        """Context manager should create client."""
        backend = HttpxBackend()
        assert backend._client is None

        with backend:
            assert backend._client is not None
            assert isinstance(backend._client, httpx.Client)

    def test_context_manager_closes_client(self) -> None:
        """Context manager should close owned client."""
        backend = HttpxBackend()

        with backend:
            client = backend._client
            assert client is not None

        assert backend._client is None

    def test_external_client_not_closed(self) -> None:
        """Should not close externally provided client."""
        with httpx.Client() as external_client:
            backend = HttpxBackend(client=external_client)

            with backend:
                pass

            assert not external_client.is_closed


# -----------------------------------------------------------------------------
# Async Lifecycle Tests
# -----------------------------------------------------------------------------


class TestHttpxAsyncBackendLifecycle:
    """Test HttpxAsyncBackend lifecycle management."""

    async def test_requires_context_manager_or_client(self) -> None:
        """Should raise error if used without client."""
        backend = HttpxAsyncBackend()

        with pytest.raises(RuntimeError, match="requires a client"):
            await backend.request("GET", "https://example.com")

    async def test_context_manager_creates_client(self) -> None:
        """Context manager should create client."""
        backend = HttpxAsyncBackend()
        assert backend._client is None

        async with backend:
            assert backend._client is not None
            assert isinstance(backend._client, httpx.AsyncClient)

    async def test_context_manager_closes_client(self) -> None:
        """Context manager should close owned client."""
        backend = HttpxAsyncBackend()

        async with backend:
            client = backend._client
            assert client is not None

        assert backend._client is None

    async def test_external_client_not_closed(self) -> None:
        """Should not close externally provided client."""
        async with httpx.AsyncClient() as external_client:
            backend = HttpxAsyncBackend(client=external_client)

            async with backend:
                pass

            assert not external_client.is_closed


# -----------------------------------------------------------------------------
# Implementation-Specific Tests
# -----------------------------------------------------------------------------


class TestHttpxBackendSpecific:
    """Tests specific to HttpxBackend implementation details."""

    def test_passes_timeout_to_client(
        self, backend: HttpxBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should pass timeout parameter to underlying client.request."""
        with mock_request(MockResponseData()) as mock:
            backend.request(
                method="GET",
                url="https://api.example.com/data",
                timeout=5.0,
            )

            mock.assert_called_once()
            assert mock.call_args[1]["timeout"] == 5.0

    def test_passes_content_parameter(
        self, backend: HttpxBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should pass content as 'content' parameter (httpx convention)."""
        with mock_request(MockResponseData()) as mock:
            backend.request(
                method="POST",
                url="https://api.example.com/data",
                content=b'{"key": "value"}',
            )

            mock.assert_called_once()
            assert mock.call_args[1]["content"] == b'{"key": "value"}'

    def test_returns_httpx_response_type(
        self, backend: HttpxBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should return HttpxResponse wrapper type."""
        with mock_request(MockResponseData()):
            response = backend.request(
                method="GET",
                url="https://api.example.com/data",
            )

            assert isinstance(response, HttpxResponse)


class TestHttpxAsyncBackendSpecific:
    """Tests specific to HttpxAsyncBackend implementation details."""

    async def test_passes_timeout_to_client(
        self, async_backend: HttpxAsyncBackend, mock_async_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should pass timeout parameter to underlying client.request."""
        with mock_async_request(MockResponseData()) as mock:
            await async_backend.request(
                method="GET",
                url="https://api.example.com/data",
                timeout=5.0,
            )

            mock.assert_called_once()
            assert mock.call_args[1]["timeout"] == 5.0

    async def test_returns_httpx_response_type(
        self, async_backend: HttpxAsyncBackend, mock_async_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should return HttpxResponse wrapper type."""
        with mock_async_request(MockResponseData()):
            response = await async_backend.request(
                method="GET",
                url="https://api.example.com/data",
            )

            assert isinstance(response, HttpxResponse)
