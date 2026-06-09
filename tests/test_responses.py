"""Tests for response handling."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel

from clientcraft import BytesResponse, Get, ResponseStyle, TextResponse, extract_endpoint_info
from clientcraft._base import HttpError
from clientcraft.client import APIClient

from .conftest import (
    DeleteUserRequest,
    GetUserRequest,
    MockBackend,
    UserAPI,
)

# ---------------------------------------------------------------------------
# Test-specific API clients (must be at module level for get_type_hints)
# ---------------------------------------------------------------------------


class HealthRequest(BaseModel):
    pass


class HealthAPI(APIClient):
    check_health: Get[HealthRequest, TextResponse, Literal["/health"]]


class DownloadRequest(BaseModel):
    file_id: str


class FileAPI(APIClient):
    download: Get[DownloadRequest, BytesResponse, Literal["/files/{file_id}"]]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResponseHandling:
    """Test different response styles."""

    def test_none_response_returns_none(self, mock_backend: MockBackend) -> None:
        """None response type should return None."""
        mock_backend.response_content = b""
        mock_backend.response_status = 204

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        result = client.delete_user(DeleteUserRequest(user_id="123"))

        assert result is None

    def test_text_response_returns_text_content(self, mock_backend: MockBackend) -> None:
        """TextResponse type should return decoded text."""
        mock_backend.response_content = b"OK - all systems operational"

        client = HealthAPI(base_url="https://api.example.com", backend=mock_backend)
        result = client.check_health(HealthRequest())

        assert isinstance(result, TextResponse)
        assert result.content == "OK - all systems operational"

    def test_bytes_response_returns_raw_bytes(self, mock_backend: MockBackend) -> None:
        """BytesResponse type should return raw bytes."""
        mock_backend.response_content = b"\x89PNG\r\n\x1a\n"

        client = FileAPI(base_url="https://api.example.com", backend=mock_backend)
        result = client.download(DownloadRequest(file_id="abc"))

        assert isinstance(result, BytesResponse)
        assert result.content == b"\x89PNG\r\n\x1a\n"

    def test_response_style_inferred_from_none_type(self) -> None:
        """ResponseStyle.NONE should be inferred from None response type."""
        from typing import get_type_hints

        hints = get_type_hints(UserAPI, include_extras=True)

        delete_extracted = extract_endpoint_info(hints["delete_user"])
        assert delete_extracted is not None
        assert delete_extracted.info.response_style == ResponseStyle.NONE

    def test_http_error_raised_on_4xx(self, mock_backend: MockBackend) -> None:
        """HTTP errors should raise HttpError exception."""
        mock_backend.response_status = 404
        mock_backend.response_content = b'{"error": "Not found"}'

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)

        with pytest.raises(HttpError) as exc_info:
            client.get_user(GetUserRequest(user_id="123"))

        assert exc_info.value.status_code == 404
        assert b"Not found" in exc_info.value.content

    def test_http_error_raised_on_5xx(self, mock_backend: MockBackend) -> None:
        """Server errors should raise HttpError exception."""
        mock_backend.response_status = 500
        mock_backend.response_content = b"Internal Server Error"

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)

        with pytest.raises(HttpError) as exc_info:
            client.get_user(GetUserRequest(user_id="123"))

        assert exc_info.value.status_code == 500


class TestHttpError:
    """Test HttpError exception."""

    def test_http_error_stores_status_code(self) -> None:
        """HttpError should store status code."""
        error = HttpError(404, b"Not found")
        assert error.status_code == 404

    def test_http_error_stores_content(self) -> None:
        """HttpError should store response content."""
        error = HttpError(500, b"Internal Server Error")
        assert error.content == b"Internal Server Error"

    def test_http_error_stores_headers(self) -> None:
        """HttpError should store response headers."""
        error = HttpError(400, b"Bad Request", {"X-Error-Code": "INVALID"})
        assert error.headers["X-Error-Code"] == "INVALID"

    def test_http_error_message_contains_status(self) -> None:
        """HttpError message should include status code."""
        error = HttpError(403, b"Forbidden")
        assert "403" in str(error)

    def test_http_error_handles_non_utf8_content(self) -> None:
        """HttpError should handle non-UTF-8 content gracefully."""
        error = HttpError(500, b"\xff\xfe")
        # Should not raise - uses 'replace' error handling
        str(error)
