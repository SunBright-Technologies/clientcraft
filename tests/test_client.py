"""Tests for the API client core functionality."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal, get_type_hints
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from clientcraft import Patch, Post, Put, RequestStyle, extract_endpoint_info
from clientcraft.client import APIClient

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


class CreateEventRequest(BaseModel):
    name: str
    starts_at: datetime


class EventAPI(APIClient):
    create_event: Post[CreateEventRequest, User, Literal["/events"]]


class CreateTokenRequest(BaseModel):
    token_id: UUID


class TokenAPI(APIClient):
    create_token: Post[CreateTokenRequest, User, Literal["/tokens"]]


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


class TestModelDumpMode:
    """Test the client-level ``model_dump_mode`` option."""

    def test_default_json_mode_serializes_datetime_in_body(self, mock_backend: MockBackend) -> None:
        """By default (``json`` mode) non-JSON-native types are coerced for the body."""
        mock_backend.response_content = b'{"id": "1", "name": "Test", "email": "t@e.com"}'

        client = EventAPI(base_url="https://api.example.com", backend=mock_backend)
        client.create_event(CreateEventRequest(name="Launch", starts_at=datetime(2026, 6, 29, 12, 0, tzinfo=UTC)))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.content is not None
        body = json.loads(mock_backend.last_request.content)
        assert body["starts_at"] == "2026-06-29T12:00:00Z"

    def test_python_mode_cannot_encode_datetime(self, mock_backend: MockBackend) -> None:
        """Opting into ``python`` mode leaves a datetime that the JSON body encoder rejects."""
        client = EventAPI(
            base_url="https://api.example.com",
            backend=mock_backend,
            model_dump_mode="python",
        )

        with pytest.raises(TypeError):
            client.create_event(CreateEventRequest(name="Launch", starts_at=datetime(2026, 6, 29, 12, 0, tzinfo=UTC)))

    def test_uuid_field_json_mode_serializes_python_mode_raises(self, mock_backend: MockBackend) -> None:
        """A UUID body field is encoded in ``json`` mode but rejected in ``python`` mode."""
        mock_backend.response_content = b'{"id": "1", "name": "Test", "email": "t@e.com"}'
        token_id = uuid4()

        # Default json mode: UUID is coerced to its string form and encodes fine.
        json_client = TokenAPI(base_url="https://api.example.com", backend=mock_backend)
        json_client.create_token(CreateTokenRequest(token_id=token_id))

        assert mock_backend.last_request is not None
        assert mock_backend.last_request.content is not None
        body = json.loads(mock_backend.last_request.content)
        assert body["token_id"] == str(token_id)

        # python mode: UUID stays a UUID object, which json.dumps cannot encode.
        python_client = TokenAPI(
            base_url="https://api.example.com",
            backend=mock_backend,
            model_dump_mode="python",
        )
        with pytest.raises(TypeError):
            python_client.create_token(CreateTokenRequest(token_id=token_id))


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


class TestErrorHandling:
    """Test the customizable error handling hook."""

    def test_default_handle_error_raises_http_error(self, mock_backend: MockBackend) -> None:
        """Default handle_error raises HttpError on status >= 400."""
        from clientcraft.client import HttpError

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
        from clientcraft.client import HttpError

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

from typing import Annotated  # noqa: E402

from clientcraft import DomainError, ErrorMap, Get, HttpError, Raises  # noqa: E402


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
        from clientcraft import HttpError

        mock_backend.response_status = 500
        client = MappedUserAPI(base_url="https://api.example.com", backend=mock_backend)
        with pytest.raises(HttpError):
            client.get_user(GetUserRequest(user_id="x"))

    def test_no_mapping_is_backward_compatible(self, mock_backend: MockBackend) -> None:
        # A plain client with no errors map / no Raises behaves exactly as before.
        from clientcraft import HttpError

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
