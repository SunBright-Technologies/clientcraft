"""Tests for endpoint type construction via metaclass."""

from __future__ import annotations

from typing import Annotated, Literal, get_origin

import pytest

from clientcraft import (
    BytesResponse,
    Delete,
    Get,
    Patch,
    Post,
    Put,
    RequestStyle,
    ResponseStyle,
    TextResponse,
    extract_endpoint_info,
)

from .conftest import CreateUserRequest, DeleteUserRequest, GetUserRequest, User


class TestEndpointTypeConstruction:
    """Test endpoint type creation via metaclass."""

    @pytest.mark.parametrize(
        ("endpoint_cls", "request_type", "response_type", "path", "expected_method", "expected_request_style"),
        [
            (Get, GetUserRequest, User, "/users/{user_id}", "GET", RequestStyle.QUERY),
            (Post, CreateUserRequest, User, "/users", "POST", RequestStyle.BODY),
            (Put, CreateUserRequest, User, "/users/{user_id}", "PUT", RequestStyle.BODY),
            (Patch, CreateUserRequest, User, "/users/{user_id}", "PATCH", RequestStyle.BODY),
            (Delete, DeleteUserRequest, None, "/users/{user_id}", "DELETE", RequestStyle.QUERY),
        ],
        ids=["get", "post", "put", "patch", "delete"],
    )
    def test_endpoint_method_and_request_style(
        self,
        endpoint_cls: type,
        request_type: type,
        response_type: type | None,
        path: str,
        expected_method: str,
        expected_request_style: RequestStyle,
    ) -> None:
        """Endpoint types should have correct HTTP method and request style."""
        endpoint_type = endpoint_cls[request_type, response_type, Literal[path]]  # type: ignore[misc]

        extracted = extract_endpoint_info(endpoint_type)
        assert extracted is not None
        assert extracted.info.method.name == expected_method
        assert extracted.info.request_style == expected_request_style

    def test_get_creates_annotated_type(self) -> None:
        """Get[...] should create an Annotated type."""
        endpoint_type = Get[GetUserRequest, User, Literal["/users/{user_id}"]]
        assert get_origin(endpoint_type) is Annotated

    @pytest.mark.parametrize(
        ("response_type", "expected_style"),
        [
            (TextResponse, ResponseStyle.TEXT),
            (BytesResponse, ResponseStyle.BYTES),
            (None, ResponseStyle.NONE),
            (User, ResponseStyle.JSON),
        ],
        ids=["text", "bytes", "none", "json"],
    )
    def test_response_style_inference(
        self,
        response_type: type | None,
        expected_style: ResponseStyle,
    ) -> None:
        """Response style should be inferred from response type."""
        # Use Delete for None response, Get for others
        if response_type is None:
            endpoint_type = Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]
        else:
            endpoint_type = Get[GetUserRequest, response_type, Literal["/test"]]  # type: ignore[misc]

        extracted = extract_endpoint_info(endpoint_type)
        assert extracted is not None
        assert extracted.info.response_style == expected_style

    def test_endpoint_type_requires_three_params(self) -> None:
        """Endpoint types should require exactly 3 type parameters."""
        with pytest.raises(TypeError, match="requires 3 type parameters"):
            Get[GetUserRequest, User]  # type: ignore[misc]

    def test_endpoint_type_requires_literal_path(self) -> None:
        """Path parameter must be a Literal string."""
        with pytest.raises(TypeError, match="Literal string"):
            Get[GetUserRequest, User, int]  # type: ignore[type-var]


class TestExtractEndpointInfo:
    """Test extract_endpoint_info function edge cases."""

    def test_returns_none_for_non_annotated(self) -> None:
        """Non-Annotated types should return None."""
        assert extract_endpoint_info(str) is None
        assert extract_endpoint_info(int) is None
        assert extract_endpoint_info(User) is None

    def test_returns_none_for_annotated_without_endpoint_info(self) -> None:
        """Annotated types without EndpointInfo should return None."""
        hint = Annotated[str, "some metadata"]
        assert extract_endpoint_info(hint) is None

    def test_extracts_request_and_response_types(self) -> None:
        """Should extract both request and response types."""
        endpoint_type = Get[GetUserRequest, User, Literal["/users/{user_id}"]]

        extracted = extract_endpoint_info(endpoint_type)
        assert extracted is not None
        assert extracted.request_type is GetUserRequest
        assert extracted.response_type is User
