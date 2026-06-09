"""Tests for response parsing."""

from __future__ import annotations

from http import HTTPMethod

from pydantic import BaseModel

from clientcraft import BytesResponse, EndpointInfo, RequestStyle, ResponseStyle, TextResponse
from clientcraft._base import parse_response

from .conftest import MockResponse, User


class TestParseResponse:
    """Test response parsing."""

    def test_parse_json_response(self) -> None:
        """JSON response should be parsed into Pydantic model."""
        response = MockResponse(
            status_code=200,
            content=b'{"id": "123", "name": "Test", "email": "test@example.com"}',
            headers={"Content-Type": "application/json"},
        )
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/users/{user_id}",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        result = parse_response(response, endpoint_info, User)

        assert isinstance(result, User)
        assert result.id == "123"
        assert result.name == "Test"

    def test_parse_text_response(self) -> None:
        """TEXT response should return TextResponse."""
        response = MockResponse(
            status_code=200,
            content=b"OK - healthy",
            headers={},
        )
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/health",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.TEXT,
        )

        result = parse_response(response, endpoint_info, TextResponse)

        assert isinstance(result, TextResponse)
        assert result.content == "OK - healthy"

    def test_parse_bytes_response(self) -> None:
        """BYTES response should return BytesResponse."""
        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00"
        response = MockResponse(
            status_code=200,
            content=binary_content,
            headers={},
        )
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/download",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.BYTES,
        )

        result = parse_response(response, endpoint_info, BytesResponse)

        assert isinstance(result, BytesResponse)
        assert result.content == binary_content

    def test_parse_none_response(self) -> None:
        """NONE response should return None."""
        response = MockResponse(status_code=204, content=b"", headers={})
        endpoint_info = EndpointInfo(
            method=HTTPMethod.DELETE,
            path="/users/{user_id}",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.NONE,
        )

        result = parse_response(response, endpoint_info, None)

        assert result is None

    def test_parse_empty_json_response(self) -> None:
        """Empty JSON response should create model with defaults."""

        class EmptyModel(BaseModel):
            field: str = "default"

        response = MockResponse(status_code=200, content=b"", headers={})
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/empty",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        result = parse_response(response, endpoint_info, EmptyModel)

        assert isinstance(result, EmptyModel)
        assert result.field == "default"
