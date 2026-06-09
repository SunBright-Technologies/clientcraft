"""Tests for RequestsBackend implementation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from clientcraft.backends.requests import RequestsBackend, RequestsResponse

from .conftest import BackendInterfaceTests, MockResponseData

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def backend() -> Iterator[RequestsBackend]:
    """Create a RequestsBackend within context manager."""
    with RequestsBackend() as b:
        yield b


@pytest.fixture
def mock_request(backend: RequestsBackend) -> Callable[[MockResponseData], Any]:
    """Create a mock request context manager for the backend."""

    @contextmanager
    def _mock(data: MockResponseData) -> Iterator[MagicMock]:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = data.status_code
        mock_response.content = data.content
        mock_response.headers = data.headers

        with patch.object(backend._session, "request", return_value=mock_response) as mock:
            yield mock

    return _mock


# -----------------------------------------------------------------------------
# Interface Tests (inherited from base class)
# -----------------------------------------------------------------------------


class TestRequestsBackendInterface(BackendInterfaceTests[RequestsBackend]):
    """Test that RequestsBackend conforms to the HttpBackend interface."""

    @pytest.fixture
    def backend(self) -> Iterator[RequestsBackend]:
        """Provide a RequestsBackend instance."""
        with RequestsBackend() as b:
            yield b

    @pytest.fixture
    def mock_request(self, backend: RequestsBackend) -> Callable[[MockResponseData], Any]:
        """Provide mock request function for RequestsBackend."""

        @contextmanager
        def _mock(data: MockResponseData) -> Iterator[MagicMock]:
            mock_response = MagicMock(spec=requests.Response)
            mock_response.status_code = data.status_code
            mock_response.content = data.content
            mock_response.headers = data.headers

            with patch.object(backend._session, "request", return_value=mock_response) as mock:
                yield mock

        return _mock


# -----------------------------------------------------------------------------
# Lifecycle Tests (specific to RequestsBackend)
# -----------------------------------------------------------------------------


class TestRequestsBackendLifecycle:
    """Test RequestsBackend lifecycle management."""

    def test_requires_context_manager_or_session(self) -> None:
        """Should raise error if used without session."""
        backend = RequestsBackend()

        with pytest.raises(RuntimeError, match="requires a session"):
            backend.request("GET", "https://example.com")

    def test_context_manager_creates_session(self) -> None:
        """Context manager should create session."""
        backend = RequestsBackend()
        assert backend._session is None

        with backend:
            assert backend._session is not None
            assert isinstance(backend._session, requests.Session)

    def test_context_manager_closes_session(self) -> None:
        """Context manager should close owned session."""
        backend = RequestsBackend()

        with backend:
            session = backend._session
            assert session is not None

        assert backend._session is None

    def test_external_session_not_closed(self) -> None:
        """Should not close externally provided session."""
        with requests.Session() as external_session:
            backend = RequestsBackend(session=external_session)

            with backend:
                pass

            assert external_session.get_adapter("https://") is not None


# -----------------------------------------------------------------------------
# Implementation-Specific Tests
# -----------------------------------------------------------------------------


class TestRequestsBackendSpecific:
    """Tests specific to RequestsBackend implementation details."""

    def test_passes_timeout_to_session(
        self, backend: RequestsBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should pass timeout parameter to underlying session.request."""
        with mock_request(MockResponseData()) as mock:
            backend.request(
                method="GET",
                url="https://api.example.com/data",
                timeout=5.0,
            )

            mock.assert_called_once()
            assert mock.call_args[1]["timeout"] == 5.0

    def test_passes_data_as_data_parameter(
        self, backend: RequestsBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should pass content as 'data' parameter (requests convention)."""
        with mock_request(MockResponseData()) as mock:
            backend.request(
                method="POST",
                url="https://api.example.com/data",
                content=b'{"key": "value"}',
            )

            mock.assert_called_once()
            assert mock.call_args[1]["data"] == b'{"key": "value"}'

    def test_returns_requests_response_type(
        self, backend: RequestsBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should return RequestsResponse wrapper type."""
        with mock_request(MockResponseData()):
            response = backend.request(
                method="GET",
                url="https://api.example.com/data",
            )

            assert isinstance(response, RequestsResponse)
