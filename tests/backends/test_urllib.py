"""Tests for UrllibBackend implementation."""

from __future__ import annotations

from contextlib import contextmanager
from http.client import HTTPResponse
from io import BytesIO
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from clientcraft.backends.urllib import UrllibBackend, UrllibResponse

from .conftest import BackendInterfaceTests, MockResponseData

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


# Patch target for urllib.request.urlopen (where it's used, not defined)
_URLOPEN_PATCH_TARGET = "clientcraft.backends.urllib.urlopen"


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


def _create_mock_response(data: MockResponseData) -> MagicMock:
    """Create a mock urllib HTTPResponse."""
    from email.message import Message

    # Create a real Message object for headers since HTTPResponse.headers is a Message
    headers_message = Message()
    for key, value in (data.headers or {}).items():
        headers_message[key] = value

    mock_response = MagicMock(spec=HTTPResponse)
    mock_response.status = data.status_code
    mock_response.read.return_value = data.content
    mock_response.headers = headers_message
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def _create_http_error(data: MockResponseData) -> HTTPError:
    """Create an HTTPError for 4xx/5xx responses."""
    fp = BytesIO(data.content)
    error = HTTPError(
        url="https://api.example.com",
        code=data.status_code,
        msg="Error",
        hdrs=data.headers or {},  # type: ignore[arg-type]
        fp=fp,
    )
    return error


@pytest.fixture
def backend() -> Iterator[UrllibBackend]:
    """Create a UrllibBackend within context manager."""
    with UrllibBackend() as b:
        yield b


@pytest.fixture
def mock_request(backend: UrllibBackend) -> Callable[[MockResponseData], Any]:
    """Create a mock request context manager."""

    @contextmanager
    def _mock(data: MockResponseData) -> Iterator[MagicMock]:
        if data.status_code >= 400:
            error = _create_http_error(data)
            with patch(_URLOPEN_PATCH_TARGET, side_effect=error) as mock:
                yield mock
        else:
            mock_response = _create_mock_response(data)
            with patch(_URLOPEN_PATCH_TARGET, return_value=mock_response) as mock:
                yield mock

    return _mock


# -----------------------------------------------------------------------------
# Interface Tests
# -----------------------------------------------------------------------------


class TestUrllibBackendInterface(BackendInterfaceTests[UrllibBackend]):
    """Test that UrllibBackend conforms to the HttpBackend interface."""

    @pytest.fixture
    def backend(self) -> Iterator[UrllibBackend]:
        """Provide a UrllibBackend instance."""
        with UrllibBackend() as b:
            yield b

    @pytest.fixture
    def mock_request(self, backend: UrllibBackend) -> Callable[[MockResponseData], Any]:
        """Provide mock request function for UrllibBackend."""

        @contextmanager
        def _mock(data: MockResponseData) -> Iterator[MagicMock]:
            if data.status_code >= 400:
                error = _create_http_error(data)
                with patch(_URLOPEN_PATCH_TARGET, side_effect=error) as mock:
                    yield mock
            else:
                mock_response = _create_mock_response(data)
                with patch(_URLOPEN_PATCH_TARGET, return_value=mock_response) as mock:
                    yield mock

        return _mock


# -----------------------------------------------------------------------------
# Lifecycle Tests
# -----------------------------------------------------------------------------


class TestUrllibBackendLifecycle:
    """Test UrllibBackend lifecycle management."""

    def test_context_manager_works(self) -> None:
        """Context manager should work without errors."""
        with UrllibBackend() as backend:
            assert backend is not None

    def test_can_be_used_without_context_manager(self) -> None:
        """Unlike other backends, urllib doesn't require context manager."""
        backend = UrllibBackend()

        with patch(_URLOPEN_PATCH_TARGET) as mock_urlopen:
            mock_response = _create_mock_response(MockResponseData())
            mock_urlopen.return_value = mock_response

            response = backend.request("GET", "https://example.com")
            assert response.status_code == 200


# -----------------------------------------------------------------------------
# Implementation-Specific Tests
# -----------------------------------------------------------------------------


class TestUrllibBackendSpecific:
    """Tests specific to UrllibBackend implementation details."""

    def test_passes_timeout_to_urlopen(
        self, backend: UrllibBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should pass timeout parameter to urlopen."""
        with mock_request(MockResponseData()) as mock:
            backend.request(
                method="GET",
                url="https://api.example.com/data",
                timeout=5.0,
            )

            mock.assert_called_once()
            assert mock.call_args[1]["timeout"] == 5.0

    def test_handles_http_error_as_response(self, backend: UrllibBackend) -> None:
        """Should handle HTTPError and return as normal response."""
        error_data = MockResponseData(
            status_code=404, content=b'{"error": "not found"}', headers={"Content-Type": "application/json"}
        )
        error = _create_http_error(error_data)

        with patch(_URLOPEN_PATCH_TARGET, side_effect=error):
            response = backend.request("GET", "https://api.example.com/missing")

            assert response.status_code == 404
            assert response.content == b'{"error": "not found"}'

    def test_returns_urllib_response_type(
        self, backend: UrllibBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should return UrllibResponse wrapper type."""
        with mock_request(MockResponseData()):
            response = backend.request(
                method="GET",
                url="https://api.example.com/data",
            )

            assert isinstance(response, UrllibResponse)

    def test_sends_body_for_post_requests(
        self, backend: UrllibBackend, mock_request: Callable[[MockResponseData], Any]
    ) -> None:
        """Should include request body for POST requests."""
        with mock_request(MockResponseData()) as mock:
            backend.request(
                method="POST",
                url="https://api.example.com/data",
                content=b'{"key": "value"}',
            )

            mock.assert_called_once()
            request = mock.call_args[0][0]
            assert request.data == b'{"key": "value"}'

    def test_sets_method_on_request(self, backend: UrllibBackend) -> None:
        """Should set correct HTTP method on request."""
        with patch(_URLOPEN_PATCH_TARGET) as mock_urlopen:
            mock_response = _create_mock_response(MockResponseData())
            mock_urlopen.return_value = mock_response

            backend.request("DELETE", "https://api.example.com/resource/1")

            request = mock_urlopen.call_args[0][0]
            assert request.get_method() == "DELETE"
