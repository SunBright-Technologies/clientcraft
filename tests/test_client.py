"""Tests for the API client core functionality."""

from __future__ import annotations

from typing import Literal, get_type_hints

from clientcraft import Patch, Put, RequestStyle, extract_endpoint_info
from clientcraft.client import APIClient
from pydantic import BaseModel

from .conftest import (
    CreateUserRequest,
    DeleteUserRequest,
    GetUserRequest,
    MockBackend,
    SearchRequest,
    User,
    UserAPI,
)

# ---------------------------------------------------------------------------
# Test-specific API clients (must be at module level for get_type_hints)
# ---------------------------------------------------------------------------


class UpdateUserRequest(BaseModel):
    user_id: str
    name: str
    email: str


class UserUpdateAPI(APIClient):
    update_user: Put[UpdateUserRequest, User, Literal["/users/{user_id}"]]


class PatchUserRequest(BaseModel):
    user_id: str
    name: str | None = None


class UserPatchAPI(APIClient):
    patch_user: Patch[PatchUserRequest, User, Literal["/users/{user_id}"]]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAPIClient:
    """Test the API client core functionality."""

    def test_get_endpoint_creates_correct_url(self, mock_backend: MockBackend) -> None:
        """GET endpoints should interpolate path params and use query string."""
        mock_backend.response_content = b'{"id": "123", "name": "Test", "email": "test@example.com"}'

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        client.get_user(GetUserRequest(user_id="123"))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.method == "GET"
        assert mock_backend.last_request.url == "https://api.example.com/users/123"
        assert mock_backend.last_request.content is None

    def test_post_endpoint_sends_body(self, mock_backend: MockBackend) -> None:
        """POST endpoints should send JSON body."""
        mock_backend.response_content = b'{"id": "456", "name": "New User", "email": "new@example.com"}'

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        client.create_user(CreateUserRequest(name="New User", email="new@example.com"))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.method == "POST"
        assert mock_backend.last_request.url == "https://api.example.com/users"
        assert mock_backend.last_request.content is not None
        assert b'"name": "New User"' in mock_backend.last_request.content

    def test_get_endpoint_sends_query_params(self, mock_backend: MockBackend) -> None:
        """GET endpoints should encode non-path params as query string."""
        mock_backend.response_content = b'{"users": []}'

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        client.search_users(SearchRequest(query="test", limit=10))

        assert mock_backend.last_request is not None
        assert "query=test" in mock_backend.last_request.url
        assert "limit=10" in mock_backend.last_request.url

    def test_delete_endpoint_returns_none(self, mock_backend: MockBackend) -> None:
        """DELETE endpoints with None response type should return None."""
        mock_backend.response_content = b""
        mock_backend.response_status = 204

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        result = client.delete_user(DeleteUserRequest(user_id="123"))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.method == "DELETE"
        assert mock_backend.last_request.content is None
        assert result is None

    def test_type_inference_works(self, mock_backend: MockBackend) -> None:
        """Result should be typed as User, not Any."""
        mock_backend.response_content = b'{"id": "123", "name": "Test", "email": "test@example.com"}'

        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        result = client.get_user(GetUserRequest(user_id="123"))

        assert result is not None
        assert result.name == "Test"
        assert isinstance(result, User)

    def test_backend_is_protocol_based(self, mock_backend: MockBackend) -> None:
        """Backend should work without inheriting from HttpBackend."""
        client = UserAPI(base_url="https://api.example.com", backend=mock_backend)
        assert client._backend is mock_backend

    def test_request_style_in_endpoint_info(self) -> None:
        """Endpoint info should contain request_style."""
        hints = get_type_hints(UserAPI, include_extras=True)

        get_extracted = extract_endpoint_info(hints["get_user"])
        assert get_extracted is not None
        assert get_extracted.info.request_style == RequestStyle.QUERY

        post_extracted = extract_endpoint_info(hints["create_user"])
        assert post_extracted is not None
        assert post_extracted.info.request_style == RequestStyle.BODY


class TestClientDefaultHeaders:
    """Test client with default headers."""

    def test_default_headers_sent_with_every_request(self, mock_backend: MockBackend) -> None:
        """Default headers should be sent with every request."""
        mock_backend.response_content = b'{"id": "1", "name": "Test", "email": "t@e.com"}'

        client = UserAPI(
            base_url="https://api.example.com",
            backend=mock_backend,
            default_headers={"Authorization": "Bearer xyz", "X-Request-Id": "req-123"},
        )
        client.get_user(GetUserRequest(user_id="1"))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.headers["Authorization"] == "Bearer xyz"
        assert mock_backend.last_request.headers["X-Request-Id"] == "req-123"


class TestPutAndPatchMethods:
    """Test PUT and PATCH HTTP methods."""

    def test_put_endpoint_sends_body(self, mock_backend: MockBackend) -> None:
        """PUT endpoints should send JSON body."""
        mock_backend.response_content = b'{"id": "123", "name": "Updated", "email": "new@example.com"}'

        client = UserUpdateAPI(base_url="https://api.example.com", backend=mock_backend)
        client.update_user(UpdateUserRequest(user_id="123", name="Updated", email="new@example.com"))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.method == "PUT"
        assert mock_backend.last_request.url == "https://api.example.com/users/123"
        assert mock_backend.last_request.content is not None
        assert b'"name": "Updated"' in mock_backend.last_request.content

    def test_patch_endpoint_sends_body(self, mock_backend: MockBackend) -> None:
        """PATCH endpoints should send JSON body."""
        mock_backend.response_content = b'{"id": "123", "name": "Patched", "email": "old@example.com"}'

        client = UserPatchAPI(base_url="https://api.example.com", backend=mock_backend)
        client.patch_user(PatchUserRequest(user_id="123", name="Patched"))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.method == "PATCH"
        assert mock_backend.last_request.content is not None
        assert b'"name": "Patched"' in mock_backend.last_request.content
