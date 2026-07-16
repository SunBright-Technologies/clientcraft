"""
Example: testing *your application* code that depends on a client.

This covers the **client -> your code** direction. Here the client is a
collaborator you inject into a service; you don't care how it talks HTTP, you just
want to stub what it returns and assert how your code used it. No backend needed.

  * `mock_client(UserAPI, get_user=...)` builds an injectable client whose
    endpoints are mocks (returning domain objects, not HTTP responses).
  * `mock_endpoint(client, "get_user", ...)` scopes an override for a block and
    restores it after — the client-side counterpart to `backend.mock_get`.
  * `mock_of(client, "get_user")` hands you the underlying mock for assertions.

Run it:

    uv run pytest examples/testing_your_app.py -v
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from clientcraft import Get, Post
from clientcraft.client import APIClient
from clientcraft.testing import mock_client, mock_endpoint, mock_of


class GetUserRequest(BaseModel):
    user_id: str


class CreateUserRequest(BaseModel):
    name: str


class User(BaseModel):
    id: str
    name: str


class UserAPI(APIClient):
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
    create_user: Post[CreateUserRequest, User, Literal["/users"]]


class GreetingService:
    """The application code under test: it depends on a UserAPI."""

    def __init__(self, users: UserAPI) -> None:
        self._users = users

    def greet(self, user_id: str) -> str:
        user = self._users.get_user(GetUserRequest(user_id=user_id))
        assert isinstance(user, User)
        return f"Hello, {user.name}!"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def users_stub() -> UserAPI:
    """An injectable fake client with one endpoint stubbed."""
    return mock_client(UserAPI, get_user=User(id="1", name="Ada"))


@pytest.fixture
def override_get_user(users_stub: UserAPI) -> Iterator[Mock]:
    """Scope an endpoint override for the test — symmetric with the backend's
    `mock_get` yield-fixture. Restores the stub's original on exit."""
    with mock_endpoint(users_stub, "get_user", return_value=User(id="1", name="Grace")) as m:
        yield m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_service_uses_injected_client(users_stub: UserAPI) -> None:
    service = GreetingService(users_stub)

    assert service.greet("1") == "Hello, Ada!"
    mock_of(users_stub, "get_user").assert_called_once_with(GetUserRequest(user_id="1"))


def test_stub_with_side_effect() -> None:
    stub = mock_client(
        UserAPI,
        get_user=Mock(side_effect=[User(id="1", name="a"), User(id="2", name="b")]),
    )
    assert stub.get_user(GetUserRequest(user_id="1")).name == "a"
    assert stub.get_user(GetUserRequest(user_id="2")).name == "b"


def test_unmocked_endpoint_fails_loudly(users_stub: UserAPI) -> None:
    # create_user was not stubbed -> calling it raises rather than passing silently.
    with pytest.raises(AssertionError, match="No mock registered"):
        users_stub.create_user(CreateUserRequest(name="Lin"))


def test_scoped_endpoint_override(users_stub: UserAPI, override_get_user: Mock) -> None:
    # override_get_user replaced the stub's default ("Ada") with "Grace"
    assert GreetingService(users_stub).greet("1") == "Hello, Grace!"
    override_get_user.assert_called_once_with(GetUserRequest(user_id="1"))
