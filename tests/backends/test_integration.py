"""
Integration tests for HTTP backends.

These tests make real HTTP requests to an httpbin server. By default they hit
the public httpbin.org; set the HTTPBIN_BASE_URL env var to target a self-hosted
instance (CI runs an httpbin container to avoid public-endpoint flakiness).
Run with: pytest -m integration
Skip with: pytest -m "not integration"

The tests are parametrized across all available backends to ensure
consistent behavior regardless of which HTTP library is used.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

from clientcraft.backends.aiohttp import AiohttpBackend
from clientcraft.backends.httpx import HttpxAsyncBackend, HttpxBackend
from clientcraft.backends.requests import RequestsBackend
from clientcraft.backends.urllib import UrllibBackend

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from clientcraft.backends import AsyncHttpBackend, HttpBackend


# Mark all tests in this module as integration tests
# Also add reruns for transient network failures
pytestmark = [
    pytest.mark.integration,
    pytest.mark.flaky(reruns=3, reruns_delay=1),
]


# -----------------------------------------------------------------------------
# Test Configuration
# -----------------------------------------------------------------------------

# Defaults to the public httpbin.org for local runs; CI overrides this to point
# at a self-hosted httpbin container to avoid public-endpoint flakiness.
HTTPBIN_BASE_URL = os.environ.get("HTTPBIN_BASE_URL", "https://httpbin.org")


# -----------------------------------------------------------------------------
# Sync Backend Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def requests_backend() -> Iterator[RequestsBackend]:
    """Provide a RequestsBackend instance."""
    with RequestsBackend() as backend:
        yield backend


@pytest.fixture
def httpx_backend() -> Iterator[HttpxBackend]:
    """Provide a HttpxBackend instance."""
    with HttpxBackend() as backend:
        yield backend


@pytest.fixture
def urllib_backend() -> Iterator[UrllibBackend]:
    """Provide a UrllibBackend instance."""
    with UrllibBackend() as backend:
        yield backend


@pytest.fixture(params=["requests", "httpx", "urllib"])
def sync_backend(
    request: pytest.FixtureRequest,
    requests_backend: RequestsBackend,
    httpx_backend: HttpxBackend,
    urllib_backend: UrllibBackend,
) -> HttpBackend:
    """Parametrized fixture providing all sync backends."""
    backends: dict[str, HttpBackend] = {
        "requests": requests_backend,
        "httpx": httpx_backend,
        "urllib": urllib_backend,
    }
    return backends[request.param]


# -----------------------------------------------------------------------------
# Async Backend Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
async def aiohttp_backend() -> AsyncIterator[AiohttpBackend]:
    """Provide an AiohttpBackend instance."""
    async with AiohttpBackend() as backend:
        yield backend


@pytest.fixture
async def httpx_async_backend() -> AsyncIterator[HttpxAsyncBackend]:
    """Provide a HttpxAsyncBackend instance."""
    async with HttpxAsyncBackend() as backend:
        yield backend


@pytest.fixture(params=["aiohttp", "httpx_async"])
async def async_backend(
    request: pytest.FixtureRequest,
    aiohttp_backend: AiohttpBackend,
    httpx_async_backend: HttpxAsyncBackend,
) -> AsyncHttpBackend:
    """Parametrized fixture providing all async backends."""
    backends: dict[str, AsyncHttpBackend] = {
        "aiohttp": aiohttp_backend,
        "httpx_async": httpx_async_backend,
    }
    return backends[request.param]


# -----------------------------------------------------------------------------
# Sync Integration Tests
# -----------------------------------------------------------------------------


class TestSyncBackendIntegration:
    """Integration tests for sync HTTP backends using real HTTP requests."""

    def test_get_request_returns_200(self, sync_backend: HttpBackend) -> None:
        """All backends should successfully make GET requests."""
        response = sync_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/get",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "headers" in data

    def test_post_request_sends_body(self, sync_backend: HttpBackend) -> None:
        """All backends should correctly send POST body."""
        body = json.dumps({"message": "hello"}).encode()

        response = sync_backend.request(
            method="POST",
            url=f"{HTTPBIN_BASE_URL}/post",
            content=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["json"] == {"message": "hello"}

    def test_custom_headers_sent(self, sync_backend: HttpBackend) -> None:
        """All backends should send custom headers."""
        response = sync_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/headers",
            headers={
                "X-Custom-Header": "test-value",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["headers"].get("X-Custom-Header") == "test-value"

    def test_404_response_not_raised(self, sync_backend: HttpBackend) -> None:
        """All backends should return 404 as response, not raise exception."""
        response = sync_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/status/404",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 404

    def test_500_response_not_raised(self, sync_backend: HttpBackend) -> None:
        """All backends should return 500 as response, not raise exception."""
        response = sync_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/status/500",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 500

    def test_put_request(self, sync_backend: HttpBackend) -> None:
        """All backends should support PUT method."""
        body = json.dumps({"updated": True}).encode()

        response = sync_backend.request(
            method="PUT",
            url=f"{HTTPBIN_BASE_URL}/put",
            content=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["json"] == {"updated": True}

    def test_delete_request(self, sync_backend: HttpBackend) -> None:
        """All backends should support DELETE method."""
        response = sync_backend.request(
            method="DELETE",
            url=f"{HTTPBIN_BASE_URL}/delete",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 200

    def test_patch_request(self, sync_backend: HttpBackend) -> None:
        """All backends should support PATCH method."""
        body = json.dumps({"patched": True}).encode()

        response = sync_backend.request(
            method="PATCH",
            url=f"{HTTPBIN_BASE_URL}/patch",
            content=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["json"] == {"patched": True}

    def test_response_headers_accessible(self, sync_backend: HttpBackend) -> None:
        """All backends should provide response headers."""
        response = sync_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/response-headers?X-Test-Header=test-value",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 200
        # httpbin returns the header we requested
        assert "X-Test-Header" in response.headers or "x-test-header" in response.headers


# -----------------------------------------------------------------------------
# Async Integration Tests
# -----------------------------------------------------------------------------


class TestAsyncBackendIntegration:
    """Integration tests for async HTTP backends using real HTTP requests."""

    async def test_get_request_returns_200(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should successfully make GET requests."""
        response = await async_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/get",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "headers" in data

    async def test_post_request_sends_body(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should correctly send POST body."""
        body = json.dumps({"message": "hello"}).encode()

        response = await async_backend.request(
            method="POST",
            url=f"{HTTPBIN_BASE_URL}/post",
            content=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["json"] == {"message": "hello"}

    async def test_custom_headers_sent(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should send custom headers."""
        response = await async_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/headers",
            headers={
                "X-Custom-Header": "test-value",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["headers"].get("X-Custom-Header") == "test-value"

    async def test_404_response_not_raised(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should return 404 as response, not raise exception."""
        response = await async_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/status/404",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 404

    async def test_500_response_not_raised(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should return 500 as response, not raise exception."""
        response = await async_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/status/500",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 500

    async def test_put_request(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should support PUT method."""
        body = json.dumps({"updated": True}).encode()

        response = await async_backend.request(
            method="PUT",
            url=f"{HTTPBIN_BASE_URL}/put",
            content=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["json"] == {"updated": True}

    async def test_delete_request(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should support DELETE method."""
        response = await async_backend.request(
            method="DELETE",
            url=f"{HTTPBIN_BASE_URL}/delete",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 200

    async def test_patch_request(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should support PATCH method."""
        body = json.dumps({"patched": True}).encode()

        response = await async_backend.request(
            method="PATCH",
            url=f"{HTTPBIN_BASE_URL}/patch",
            content=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "api-client-test/1.0",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["json"] == {"patched": True}

    async def test_response_headers_accessible(self, async_backend: AsyncHttpBackend) -> None:
        """All async backends should provide response headers."""
        response = await async_backend.request(
            method="GET",
            url=f"{HTTPBIN_BASE_URL}/response-headers?X-Test-Header=test-value",
            headers={"User-Agent": "api-client-test/1.0"},
        )

        assert response.status_code == 200
        assert "X-Test-Header" in response.headers or "x-test-header" in response.headers
