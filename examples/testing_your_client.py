"""
Example: testing *your client* with clientcraft.testing.FakeBackend.

This covers the **backend -> client** direction: you fake the transport (canned
HTTP responses) and let the real client run — so serialization, path building,
response parsing, and error handling are all exercised for real. Use this to test
that your `UserAPI` declaration behaves the way you think.

Routes are backed by `unittest.mock.Mock`, so you get `return_value`/`side_effect`
and call assertions, plus stack-scoped overrides that nest and restore.

Run it (a normal pytest module, kept out of the main suite by testpaths):

    uv run pytest examples/testing_your_client.py -v
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from clientcraft import AsyncGet, Get, HttpError, Post
from clientcraft.async_client import AsyncAPIClient
from clientcraft.client import APIClient
from clientcraft.testing import FakeAsyncBackend, FakeBackend, FakeResponse


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


class AsyncUserAPI(AsyncAPIClient):
    get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake() -> FakeBackend:
    """A fresh fake backend per test."""
    return FakeBackend()


@pytest.fixture
def client(fake: FakeBackend) -> UserAPI:
    """A real client wired to the fake backend."""
    return UserAPI(base_url="https://api.example.com", backend=fake)


@pytest.fixture
def user_route(fake: FakeBackend) -> Iterator[Mock]:
    """Register GET /users/1 for the test and yield its mock for assertions.

    The yield-fixture keeps the route active for the test and tears it down
    afterwards.
    """
    with fake.mock_get("/users/1", json={"id": "1", "name": "Ada"}) as m:
        yield m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_response_is_parsed_into_the_model(client: UserAPI, user_route: Mock) -> None:
    user = client.get_user(GetUserRequest(user_id="1"))

    assert user == User(id="1", name="Ada")
    user_route.assert_called_once()


def test_request_serialization_is_recorded(client: UserAPI, fake: FakeBackend) -> None:
    with fake.mock_post("/users", json={"id": "9", "name": "Lin"}) as m:
        client.create_user(CreateUserRequest(name="Lin"))

    sent = m.call_args.args[0]
    assert sent.method == "POST"
    assert sent.url.endswith("/users")
    assert sent.json() == {"name": "Lin"}


@pytest.mark.parametrize("status", [404, 500])
def test_error_status_runs_real_error_handling(client: UserAPI, fake: FakeBackend, status: int) -> None:
    with fake.mock_get("/users/999", status=status, json={"detail": "boom"}):
        with pytest.raises(HttpError) as exc_info:
            client.get_user(GetUserRequest(user_id="999"))

    assert exc_info.value.status_code == status


def test_side_effect_sequence(client: UserAPI, fake: FakeBackend) -> None:
    with fake.mock_get("/users/1") as m:
        m.side_effect = [
            FakeResponse(200, b'{"id":"1","name":"first"}', {}),
            FakeResponse(200, b'{"id":"1","name":"second"}', {}),
        ]
        assert client.get_user(GetUserRequest(user_id="1")).name == "first"
        assert client.get_user(GetUserRequest(user_id="1")).name == "second"


def test_side_effect_simulates_transport_failure(client: UserAPI, fake: FakeBackend) -> None:
    with fake.mock_get("/users/1") as m:
        m.side_effect = ConnectionError("boom")
        with pytest.raises(ConnectionError, match="boom"):
            client.get_user(GetUserRequest(user_id="1"))


def test_nested_registration_overrides_then_restores(client: UserAPI, fake: FakeBackend, user_route: Mock) -> None:
    assert client.get_user(GetUserRequest(user_id="1")).name == "Ada"

    with fake.mock_get("/users/1", json={"id": "1", "name": "override"}):
        assert client.get_user(GetUserRequest(user_id="1")).name == "override"

    # inner block popped -> fixture's registration restored
    assert client.get_user(GetUserRequest(user_id="1")).name == "Ada"


def test_unexpected_call_fails_loudly(client: UserAPI) -> None:
    with pytest.raises(AssertionError, match="No mock registered"):
        client.get_user(GetUserRequest(user_id="1"))


# ---------------------------------------------------------------------------
# Async — same fixtures/patterns, awaited (asyncio_mode = auto)
# ---------------------------------------------------------------------------


@pytest.fixture
def async_fake() -> FakeAsyncBackend:
    return FakeAsyncBackend()


@pytest.fixture
def async_client(async_fake: FakeAsyncBackend) -> AsyncUserAPI:
    return AsyncUserAPI(base_url="https://api.example.com", backend=async_fake)


async def test_async_get_user(async_client: AsyncUserAPI, async_fake: FakeAsyncBackend) -> None:
    with async_fake.mock_get("/users/5", json={"id": "5", "name": "Async"}) as m:
        user = await async_client.get_user(GetUserRequest(user_id="5"))

    assert user == User(id="5", name="Async")
    m.assert_called_once()
