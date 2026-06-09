"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import pytest
from pydantic import BaseModel

from clientcraft import Delete, Get, Post
from clientcraft._base import PreparedRequest
from clientcraft.client import APIClient

# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Ensure at least 4 workers when running with xdist."""
    # Only adjust if xdist is being used with 'auto'
    if hasattr(config.option, "numprocesses"):
        numprocesses = config.option.numprocesses
        if numprocesses == "auto":
            # Get CPU count, default to 4 if can't determine
            cpu_count = os.cpu_count() or 4
            # Use at least 4 workers
            config.option.numprocesses = max(cpu_count, 4)


# ---------------------------------------------------------------------------
# Common test models
# ---------------------------------------------------------------------------


class GetUserRequest(BaseModel):
    user_id: str


class User(BaseModel):
    id: str
    name: str
    email: str


class CreateUserRequest(BaseModel):
    name: str
    email: str


class SearchRequest(BaseModel):
    query: str
    limit: int | None = None


class UserList(BaseModel):
    users: list[User]


class DeleteUserRequest(BaseModel):
    user_id: str


# ---------------------------------------------------------------------------
# Test client
# ---------------------------------------------------------------------------


class UserAPI(APIClient):
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
    create_user: Post[CreateUserRequest, User, Literal["/users"]]
    search_users: Get[SearchRequest, UserList, Literal["/users/search"]]
    delete_user: Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------


@dataclass
class MockResponse:
    """Mock response that satisfies HttpResponse protocol."""

    status_code: int
    content: bytes
    headers: dict[str, str]


class MockBackend:
    """Mock backend that satisfies HttpBackend protocol."""

    def __init__(self) -> None:
        self.last_request: PreparedRequest | None = None
        self.response_content: bytes = b"{}"
        self.response_status: int = 200

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> MockResponse:
        self.last_request = PreparedRequest(
            method=method,
            url=url,
            content=content,
            headers=headers or {},
        )
        return MockResponse(
            status_code=self.response_status,
            content=self.response_content,
            headers={"Content-Type": "application/json"},
        )


class AsyncMockBackend:
    """Async mock backend that satisfies AsyncHttpBackend protocol."""

    def __init__(self) -> None:
        self.last_request: PreparedRequest | None = None
        self.response_content: bytes = b"{}"
        self.response_status: int = 200

    async def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> MockResponse:
        self.last_request = PreparedRequest(
            method=method,
            url=url,
            content=content,
            headers=headers or {},
        )
        return MockResponse(
            status_code=self.response_status,
            content=self.response_content,
            headers={"Content-Type": "application/json"},
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_backend() -> MockBackend:
    """Create a mock backend."""
    return MockBackend()


@pytest.fixture
def async_mock_backend() -> AsyncMockBackend:
    """Create an async mock backend."""
    return AsyncMockBackend()


@pytest.fixture
def user_api(mock_backend: MockBackend) -> UserAPI:
    """Create a UserAPI client with mock backend."""
    return UserAPI(base_url="https://api.example.com", backend=mock_backend)
