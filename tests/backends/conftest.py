"""
Shared fixtures and base test classes for HTTP backend tests.

This module provides:
- Abstract base test classes that define the common interface behavior
- Shared fixtures for mock responses
- Utilities for backend testing
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class MockResponseData:
    """Data for creating mock HTTP responses."""

    status_code: int = 200
    content: bytes = b'{"key": "value"}'
    headers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {"Content-Type": "application/json"}


@pytest.fixture
def success_response_data() -> MockResponseData:
    """Default successful response data."""
    return MockResponseData()


@pytest.fixture
def error_404_response_data() -> MockResponseData:
    """404 error response data."""
    return MockResponseData(
        status_code=404,
        content=b'{"error": "not found"}',
    )


@pytest.fixture
def error_500_response_data() -> MockResponseData:
    """500 error response data."""
    return MockResponseData(
        status_code=500,
        content=b"Internal Server Error",
        headers={},
    )


class BackendInterfaceTests[BackendT](ABC):
    """
    Abstract base class defining tests for the common HTTP backend interface.

    All sync backends must pass these tests, ensuring consistent behavior
    across different implementations (requests, httpx, urllib).

    Subclasses must implement the abstract fixtures to provide:
    - A configured backend instance
    - A way to mock the underlying HTTP calls
    """

    @pytest.fixture
    @abstractmethod
    def backend(self) -> BackendT:
        """Provide a backend instance ready for use."""
        ...

    @pytest.fixture
    @abstractmethod
    def mock_request(
        self, backend: BackendT, success_response_data: MockResponseData
    ) -> Callable[[MockResponseData], Any]:
        """
        Provide a function that mocks the backend's HTTP requests.

        Returns a context manager or function that, when called with MockResponseData,
        configures the backend to return that response.
        """
        ...

    # -------------------------------------------------------------------------
    # Interface behavior tests
    # -------------------------------------------------------------------------

    def test_returns_status_code(
        self,
        backend: BackendT,
        mock_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should return response with correct status code."""
        with mock_request(success_response_data):
            response = backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/data",
            )
            assert response.status_code == 200

    def test_returns_content(
        self,
        backend: BackendT,
        mock_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should return response with correct content."""
        with mock_request(success_response_data):
            response = backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/data",
            )
            assert response.content == b'{"key": "value"}'

    def test_returns_headers(
        self,
        backend: BackendT,
        mock_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should return response with headers as dict."""
        with mock_request(success_response_data):
            response = backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/data",
            )
            assert isinstance(response.headers, dict)
            assert "Content-Type" in response.headers or "content-type" in response.headers

    def test_handles_error_status_without_raising(
        self,
        backend: BackendT,
        mock_request: Callable[[MockResponseData], Any],
        error_404_response_data: MockResponseData,
    ) -> None:
        """Backend should return 4xx responses without raising exceptions."""
        with mock_request(error_404_response_data):
            response = backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/missing",
            )
            assert response.status_code == 404

    def test_handles_server_error_without_raising(
        self,
        backend: BackendT,
        mock_request: Callable[[MockResponseData], Any],
        error_500_response_data: MockResponseData,
    ) -> None:
        """Backend should return 5xx responses without raising exceptions."""
        with mock_request(error_500_response_data):
            response = backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/error",
            )
            assert response.status_code == 500

    def test_supports_post_with_content(
        self,
        backend: BackendT,
        mock_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should accept POST requests with body content."""
        with mock_request(success_response_data):
            response = backend.request(  # type: ignore[attr-defined]
                method="POST",
                url="https://api.example.com/data",
                content=b'{"key": "value"}',
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200

    def test_supports_custom_headers(
        self,
        backend: BackendT,
        mock_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should accept custom headers."""
        with mock_request(success_response_data):
            response = backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/data",
                headers={"Authorization": "Bearer token", "X-Custom": "value"},
            )
            assert response.status_code == 200


class AsyncBackendInterfaceTests[BackendT](ABC):
    """
    Abstract base class defining tests for async HTTP backend interface.

    All async backends must pass these tests.
    """

    @pytest.fixture
    @abstractmethod
    async def async_backend(self) -> BackendT:
        """Provide an async backend instance ready for use."""
        ...

    @pytest.fixture
    @abstractmethod
    def mock_async_request(
        self, async_backend: BackendT, success_response_data: MockResponseData
    ) -> Callable[[MockResponseData], Any]:
        """Provide a function that mocks the async backend's HTTP requests."""
        ...

    # -------------------------------------------------------------------------
    # Interface behavior tests (async versions)
    # -------------------------------------------------------------------------

    async def test_returns_status_code(
        self,
        async_backend: BackendT,
        mock_async_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should return response with correct status code."""
        with mock_async_request(success_response_data):
            response = await async_backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/data",
            )
            assert response.status_code == 200

    async def test_returns_content(
        self,
        async_backend: BackendT,
        mock_async_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should return response with correct content."""
        with mock_async_request(success_response_data):
            response = await async_backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/data",
            )
            assert response.content == b'{"key": "value"}'

    async def test_handles_error_status_without_raising(
        self,
        async_backend: BackendT,
        mock_async_request: Callable[[MockResponseData], Any],
        error_404_response_data: MockResponseData,
    ) -> None:
        """Backend should return 4xx responses without raising exceptions."""
        with mock_async_request(error_404_response_data):
            response = await async_backend.request(  # type: ignore[attr-defined]
                method="GET",
                url="https://api.example.com/missing",
            )
            assert response.status_code == 404

    async def test_supports_post_with_content(
        self,
        async_backend: BackendT,
        mock_async_request: Callable[[MockResponseData], Any],
        success_response_data: MockResponseData,
    ) -> None:
        """Backend should accept POST requests with body content."""
        with mock_async_request(success_response_data):
            response = await async_backend.request(  # type: ignore[attr-defined]
                method="POST",
                url="https://api.example.com/data",
                content=b'{"key": "value"}',
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
