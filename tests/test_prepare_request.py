"""Tests for request preparation utilities."""

from __future__ import annotations

import json
from http import HTTPMethod

import pytest
from clientcraft import EndpointInfo, RequestStyle, ResponseStyle
from clientcraft._base import (
    extract_path_params,
    prepare_request,
    serialize_query_value,
)
from pydantic import BaseModel

from .conftest import CreateUserRequest, GetUserRequest, SearchRequest


class TestPrepareRequest:
    """Test request preparation utilities."""

    def test_path_param_interpolation(self) -> None:
        """Path parameters should be interpolated into URL."""
        request = GetUserRequest(user_id="abc123")
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/users/{user_id}",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        prepared = prepare_request(
            request=request,
            endpoint_info=endpoint_info,
            path_params={"user_id"},
            base_url="https://api.example.com",
            default_headers={},
        )

        assert prepared.url == "https://api.example.com/users/abc123"
        assert prepared.content is None

    def test_missing_path_param_raises_error(self) -> None:
        """Missing path parameters should raise ValueError."""

        class IncompleteRequest(BaseModel):
            other_field: str

        request = IncompleteRequest(other_field="value")
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/users/{user_id}",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        with pytest.raises(ValueError, match="Path parameter 'user_id' not found"):
            prepare_request(
                request=request,
                endpoint_info=endpoint_info,
                path_params={"user_id"},
                base_url="https://api.example.com",
                default_headers={},
            )

    def test_query_params_serialization(self) -> None:
        """Non-path params should be serialized to query string for QUERY style."""
        request = SearchRequest(query="test search", limit=25)
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/search",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        prepared = prepare_request(
            request=request,
            endpoint_info=endpoint_info,
            path_params=set(),
            base_url="https://api.example.com",
            default_headers={},
        )

        assert "query=test+search" in prepared.url or "query=test%20search" in prepared.url
        assert "limit=25" in prepared.url

    def test_body_serialization(self) -> None:
        """Non-path params should be serialized to JSON body for BODY style."""
        request = CreateUserRequest(name="Test User", email="test@example.com")
        endpoint_info = EndpointInfo(
            method=HTTPMethod.POST,
            path="/users",
            request_style=RequestStyle.BODY,
            response_style=ResponseStyle.JSON,
        )

        prepared = prepare_request(
            request=request,
            endpoint_info=endpoint_info,
            path_params=set(),
            base_url="https://api.example.com",
            default_headers={},
        )

        assert prepared.content is not None
        body = json.loads(prepared.content)
        assert body["name"] == "Test User"
        assert body["email"] == "test@example.com"

    def test_default_headers_merged(self) -> None:
        """Default headers should be merged into request."""
        request = GetUserRequest(user_id="123")
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/users/{user_id}",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        prepared = prepare_request(
            request=request,
            endpoint_info=endpoint_info,
            path_params={"user_id"},
            base_url="https://api.example.com",
            default_headers={"Authorization": "Bearer token123", "X-Custom": "value"},
        )

        assert prepared.headers["Authorization"] == "Bearer token123"
        assert prepared.headers["X-Custom"] == "value"
        assert prepared.headers["Content-Type"] == "application/json"

    def test_base_url_trailing_slash_handled(self) -> None:
        """Trailing slashes in base_url should be handled correctly."""
        request = GetUserRequest(user_id="123")
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/users/{user_id}",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        prepared = prepare_request(
            request=request,
            endpoint_info=endpoint_info,
            path_params={"user_id"},
            base_url="https://api.example.com/",
            default_headers={},
        )

        # Should not have double slashes
        assert "//" not in prepared.url.replace("https://", "")

    def test_none_values_excluded_from_request(self) -> None:
        """None values should be excluded from query params and body."""
        request = SearchRequest(query="test", limit=None)
        endpoint_info = EndpointInfo(
            method=HTTPMethod.GET,
            path="/search",
            request_style=RequestStyle.QUERY,
            response_style=ResponseStyle.JSON,
        )

        prepared = prepare_request(
            request=request,
            endpoint_info=endpoint_info,
            path_params=set(),
            base_url="https://api.example.com",
            default_headers={},
        )

        assert "limit" not in prepared.url


class TestSerializeQueryValue:
    """Test query value serialization."""

    def test_bool_true_serialized_as_lowercase(self) -> None:
        """True should serialize as 'true'."""
        assert serialize_query_value(True) == "true"

    def test_bool_false_serialized_as_lowercase(self) -> None:
        """False should serialize as 'false'."""
        assert serialize_query_value(False) == "false"

    def test_list_serialized_as_comma_separated(self) -> None:
        """Lists should serialize as comma-separated values."""
        assert serialize_query_value(["a", "b", "c"]) == "a,b,c"
        assert serialize_query_value([1, 2, 3]) == "1,2,3"

    def test_string_passthrough(self) -> None:
        """Strings should pass through unchanged."""
        assert serialize_query_value("hello") == "hello"

    def test_int_converted_to_string(self) -> None:
        """Integers should be converted to strings."""
        assert serialize_query_value(42) == "42"


class TestExtractPathParams:
    """Test path parameter extraction."""

    def test_extracts_single_param(self) -> None:
        """Should extract single path parameter."""
        assert extract_path_params("/users/{user_id}") == {"user_id"}

    def test_extracts_multiple_params(self) -> None:
        """Should extract multiple path parameters."""
        params = extract_path_params("/orgs/{org_id}/users/{user_id}/posts/{post_id}")
        assert params == {"org_id", "user_id", "post_id"}

    def test_returns_empty_set_for_no_params(self) -> None:
        """Should return empty set when no params."""
        assert extract_path_params("/users") == set()
        assert extract_path_params("/health/check") == set()
