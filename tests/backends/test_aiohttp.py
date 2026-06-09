"""Tests for AiohttpBackend implementation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clientcraft.backends.aiohttp import AiohttpBackend, AiohttpResponse

from .conftest import AsyncBackendInterfaceTests, MockResponseData

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

# Try to import aiohttp for type checking
try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore[assignment]


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
async def async_backend() -> AsyncIterator[AiohttpBackend]:
    """Create an AiohttpBackend within async context manager."""
    async with AiohttpBackend() as b:
        yield b


@pytest.fixture
def mock_async_request(async_backend: AiohttpBackend) -> Callable[[MockResponseData], Any]:
    """Create a mock request context manager for the async backend."""

    @contextmanager
    def _mock(data: MockResponseData) -> Iterator[AsyncMock]:
        mock_response = MagicMock()
        mock_response.status = data.status_code
        mock_response.read = AsyncMock(return_value=data.content)
        mock_response.headers = data.headers or {}

        with patch.object(
            async_backend._session, "request", new_callable=MagicMock
        ) as mock_request_method:
            # Create an async context manager mock
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_request_method.return_value = mock_cm

            yield mock_request_method

    return _mock


# -----------------------------------------------------------------------------
# Interface Tests
# -----------------------------------------------------------------------------


class TestAiohttpBackendInterface(AsyncBackendInterfaceTests[AiohttpBackend]):
    """Test that AiohttpBackend conforms to the AsyncHttpBackend interface."""

    @pytest.fixture
    async def async_backend(self) -> AsyncIterator[AiohttpBackend]:
        """Provide an AiohttpBackend instance."""
        async with AiohttpBackend() as b:
            yield b

    @pytest.fixture
    def mock_async_request(
        self, async_backend: AiohttpBackend
    ) -> Callable[[MockResponseData], Any]:
        """Provide mock request function for AiohttpBackend."""

        @contextmanager
        def _mock(data: MockResponseData) -> Iterator[AsyncMock]:
            mock_response = MagicMock()
            mock_response.status = data.status_code
            mock_response.read = AsyncMock(return_value=data.content)
            mock_response.headers = data.headers or {}

            with patch.object(
                async_backend._session, "request", new_callable=MagicMock
            ) as mock_request_method:
                mock_cm = AsyncMock()
                mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_cm.__aexit__ = AsyncMock(return_value=None)
                mock_request_method.return_value = mock_cm

                yield mock_request_method

        return _mock


# -----------------------------------------------------------------------------
# Lifecycle Tests
# -----------------------------------------------------------------------------


class TestAiohttpBackendLifecycle:
    """Test AiohttpBackend lifecycle management."""

    async def test_requires_context_manager_or_session(self) -> None:
        """Should raise error if used without session."""
        backend = AiohttpBackend()

        with pytest.raises(RuntimeError, match="requires a session"):
            await backend.request("GET", "https://example.com")

    async def test_context_manager_creates_session(self) -> None:
        """Context manager should create session."""
        backend = AiohttpBackend()
        assert backend._session is None

        async with backend:
            assert backend._session is not None

    async def test_context_manager_closes_session(self) -> None:
        """Context manager should close owned session."""
        backend = AiohttpBackend()

        async with backend:
            session = backend._session
            assert session is not None

        assert backend._session is None

    @pytest.mark.skipif(aiohttp is None, reason="aiohttp not installed")
    async def test_external_session_not_closed(self) -> None:
        """Should not close externally provided session."""
        import aiohttp as aiohttp_lib  # Import inside to satisfy type checker

        async with aiohttp_lib.ClientSession() as external_session:
            backend = AiohttpBackend(session=external_session)

            async with backend:
                pass

            assert not external_session.closed


# -----------------------------------------------------------------------------
# Implementation-Specific Tests
# -----------------------------------------------------------------------------


class TestAiohttpBackendSpecific:
    """Tests specific to AiohttpBackend implementation details."""

    async def test_passes_timeout_to_request(
        self,
        async_backend: AiohttpBackend,
        mock_async_request: Callable[[MockResponseData], Any],
    ) -> None:
        """Should pass timeout parameter to underlying session.request."""
        with mock_async_request(MockResponseData()) as mock:
            await async_backend.request(
                method="GET",
                url="https://api.example.com/data",
                timeout=5.0,
            )

            mock.assert_called_once()
            # aiohttp uses ClientTimeout object
            call_kwargs = mock.call_args[1]
            assert "timeout" in call_kwargs

    async def test_passes_data_parameter(
        self,
        async_backend: AiohttpBackend,
        mock_async_request: Callable[[MockResponseData], Any],
    ) -> None:
        """Should pass content as 'data' parameter (aiohttp convention)."""
        with mock_async_request(MockResponseData()) as mock:
            await async_backend.request(
                method="POST",
                url="https://api.example.com/data",
                content=b'{"key": "value"}',
            )

            mock.assert_called_once()
            call_kwargs = mock.call_args[1]
            assert call_kwargs["data"] == b'{"key": "value"}'

    async def test_returns_aiohttp_response_type(
        self,
        async_backend: AiohttpBackend,
        mock_async_request: Callable[[MockResponseData], Any],
    ) -> None:
        """Should return AiohttpResponse wrapper type."""
        with mock_async_request(MockResponseData()):
            response = await async_backend.request(
                method="GET",
                url="https://api.example.com/data",
            )

            assert isinstance(response, AiohttpResponse)
