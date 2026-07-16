"""Tests for the testing helpers (clientcraft.testing)."""

from __future__ import annotations

import asyncio
from typing import Literal

import pytest
from pydantic import BaseModel

from clientcraft import AsyncGet, Get, Post
from clientcraft.async_client import AsyncAPIClient
from clientcraft.client import APIClient
from clientcraft.testing import (
    FakeAsyncBackend,
    FakeBackend,
    FakeResponse,
    mock_client,
    mock_endpoint,
    mock_of,
)


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


def _client(backend: FakeBackend) -> UserAPI:
    return UserAPI(base_url="https://api.example.com", backend=backend)


class TestFakeBackend:
    def test_canned_json_response_is_parsed(self) -> None:
        backend = FakeBackend()
        with backend.mock_get("/users/123", json={"id": "123", "name": "Ada"}):
            user = _client(backend).get_user(GetUserRequest(user_id="123"))
        assert user == User(id="123", name="Ada")

    def test_yielded_mock_records_the_call(self) -> None:
        backend = FakeBackend()
        with backend.mock_post("/users", json={"id": "9", "name": "Lin"}) as m:
            _client(backend).create_user(CreateUserRequest(name="Lin"))

        m.assert_called_once()
        recorded = m.call_args.args[0]
        assert recorded.method == "POST"
        assert recorded.url == "https://api.example.com/users"
        assert recorded.json() == {"name": "Lin"}

    def test_accepts_pydantic_model_and_custom_response(self) -> None:
        backend = FakeBackend()
        with backend.mock_get("/users/1", json=User(id="1", name="Grace")):
            assert _client(backend).get_user(GetUserRequest(user_id="1")).name == "Grace"

        with backend.mock_get("/users/2", response=FakeResponse(200, b'{"id":"2","name":"Ada"}', {})):
            assert _client(backend).get_user(GetUserRequest(user_id="2")).name == "Ada"

    def test_status_drives_error_handling(self) -> None:
        from clientcraft import HttpError

        backend = FakeBackend()
        with backend.mock_get("/users/999", status=404, json={"detail": "nope"}):
            with pytest.raises(HttpError) as exc_info:
                _client(backend).get_user(GetUserRequest(user_id="999"))
        assert exc_info.value.status_code == 404

    def test_side_effect_simulates_transport_error(self) -> None:
        backend = FakeBackend()
        with backend.mock_get("/users/1") as m:
            m.side_effect = ConnectionError("boom")
            with pytest.raises(ConnectionError, match="boom"):
                _client(backend).get_user(GetUserRequest(user_id="1"))

    def test_side_effect_sequence(self) -> None:
        backend = FakeBackend()
        with backend.mock_get("/users/1") as m:
            m.side_effect = [
                FakeResponse(200, b'{"id":"1","name":"first"}', {}),
                FakeResponse(200, b'{"id":"1","name":"second"}', {}),
            ]
            client = _client(backend)
            assert client.get_user(GetUserRequest(user_id="1")).name == "first"
            assert client.get_user(GetUserRequest(user_id="1")).name == "second"

    def test_unmatched_request_raises_helpful_error(self) -> None:
        backend = FakeBackend()
        with pytest.raises(AssertionError, match="No mock registered for GET"):
            _client(backend).get_user(GetUserRequest(user_id="1"))

    def test_stack_override_and_restore(self) -> None:
        backend = FakeBackend()
        client = _client(backend)
        with backend.mock_get("/users/1", json={"id": "1", "name": "outer"}):
            assert client.get_user(GetUserRequest(user_id="1")).name == "outer"

            # inner registration overrides for the duration of its block...
            with backend.mock_get("/users/1", json={"id": "1", "name": "inner"}):
                assert client.get_user(GetUserRequest(user_id="1")).name == "inner"

            # ...and is popped on exit, restoring the outer one.
            assert client.get_user(GetUserRequest(user_id="1")).name == "outer"

    def test_route_removed_after_block(self) -> None:
        backend = FakeBackend()
        with backend.mock_get("/users/1", json={"id": "1", "name": "Ada"}):
            pass
        with pytest.raises(AssertionError):
            _client(backend).get_user(GetUserRequest(user_id="1"))


class TestFakeAsyncBackend:
    def test_async_canned_response_and_recording(self) -> None:
        backend = FakeAsyncBackend()
        client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)

        with backend.mock_get("/users/5", json={"id": "5", "name": "Async"}) as m:

            async def run() -> User:
                result = await client.get_user(GetUserRequest(user_id="5"))
                assert isinstance(result, User)
                return result

            user = asyncio.run(run())

        assert user.name == "Async"
        m.assert_called_once()
        assert m.call_args.args[0].url.endswith("/users/5")


class TestMockClient:
    def test_returns_injectable_client_with_canned_returns(self) -> None:
        client = mock_client(UserAPI, get_user=User(id="1", name="Ada"))
        assert isinstance(client, UserAPI)

        result = client.get_user(GetUserRequest(user_id="1"))
        assert result == User(id="1", name="Ada")

    def test_mock_of_enables_assertions(self) -> None:
        client = mock_client(UserAPI, get_user=User(id="1", name="Ada"))
        client.get_user(GetUserRequest(user_id="1"))

        mock_of(client, "get_user").assert_called_once_with(GetUserRequest(user_id="1"))

    def test_accepts_a_prebuilt_mock_with_side_effect(self) -> None:
        from unittest.mock import Mock

        client = mock_client(
            UserAPI,
            get_user=Mock(side_effect=[User(id="1", name="a"), User(id="2", name="b")]),
        )
        assert client.get_user(GetUserRequest(user_id="1")).name == "a"
        assert client.get_user(GetUserRequest(user_id="2")).name == "b"

    def test_unmocked_endpoint_call_fails_loudly(self) -> None:
        # create_user is not stubbed -> hits the empty fake backend and raises.
        client = mock_client(UserAPI, get_user=User(id="1", name="Ada"))
        with pytest.raises(AssertionError, match="No mock registered"):
            client.create_user(CreateUserRequest(name="Lin"))

    def test_unknown_endpoint_name_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="has no endpoint 'nope'"):
            mock_client(UserAPI, nope=User(id="1", name="Ada"))

    def test_mock_of_on_unmocked_raises(self) -> None:
        client = mock_client(UserAPI, get_user=User(id="1", name="Ada"))
        with pytest.raises(TypeError, match="not mocked"):
            mock_of(client, "create_user")


class TestMockEndpoint:
    def test_scoped_override_of_real_client(self) -> None:
        backend = FakeBackend()
        client = UserAPI(base_url="https://api.example.com", backend=backend)

        with mock_endpoint(client, "get_user", return_value=User(id="1", name="Ada")) as m:
            assert client.get_user(GetUserRequest(user_id="1")) == User(id="1", name="Ada")
            m.assert_called_once_with(GetUserRequest(user_id="1"))

        # restored: real endpoint again -> hits the (empty) backend and raises
        with pytest.raises(AssertionError, match="No mock registered"):
            client.get_user(GetUserRequest(user_id="1"))

    def test_overrides_and_restores_a_mock_client_endpoint(self) -> None:
        client = mock_client(UserAPI, get_user=User(id="1", name="base"))
        assert client.get_user(GetUserRequest(user_id="1")).name == "base"

        with mock_endpoint(client, "get_user", return_value=User(id="1", name="override")):
            assert client.get_user(GetUserRequest(user_id="1")).name == "override"

        # restored to the mock_client's original stub
        assert client.get_user(GetUserRequest(user_id="1")).name == "base"

    def test_side_effect(self) -> None:
        client = mock_client(UserAPI, get_user=User(id="0", name="base"))
        with mock_endpoint(client, "get_user") as m:
            m.side_effect = [User(id="1", name="a"), User(id="2", name="b")]
            assert client.get_user(GetUserRequest(user_id="1")).name == "a"
            assert client.get_user(GetUserRequest(user_id="2")).name == "b"

    def test_unknown_endpoint_rejected(self) -> None:
        client = UserAPI(base_url="https://x", backend=FakeBackend())
        with pytest.raises(TypeError, match="has no endpoint 'nope'"):
            with mock_endpoint(client, "nope"):
                pass
