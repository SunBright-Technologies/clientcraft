"""
httpx backend implementation.

This module provides both sync and async HTTP backends using the httpx library.
Requires: `pip install httpx` or `uv add "api-client[httpx]"`

Example usage (async):
    from clientcraft.backends.httpx import HttpxAsyncBackend
    from clientcraft.async_client import AsyncAPIClient

    class UserAPI(AsyncAPIClient):
        get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]

    async with HttpxAsyncBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = await client.get_user(GetUserRequest(user_id="123"))

Example usage (sync):
    from clientcraft.backends.httpx import HttpxBackend
    from clientcraft.client import APIClient

    class UserAPI(APIClient):
        get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]

    with HttpxBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = client.get_user(GetUserRequest(user_id="123"))
"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType

try:
    import httpx
except ImportError as e:
    raise ImportError(
        "httpx is required for HttpxBackend/HttpxAsyncBackend. "
        "Install it with: pip install httpx or uv add 'api-client[httpx]'"
    ) from e


@dataclass
class HttpxResponse:
    """
    Wrapper around httpx.Response to satisfy HttpResponse protocol.

    httpx.Response has status_code and content, but headers is a
    httpx.Headers object, so we normalize to a plain dict.
    """

    status_code: int
    content: bytes
    headers: dict[str, str]


# ---------------------------------------------------------------------------
# Async Backend
# ---------------------------------------------------------------------------


class HttpxAsyncBackend:
    """
    Async HTTP backend using httpx.

    Can be used as an async context manager for automatic client management,
    or initialized with an existing client for more control.

    Example as context manager:
        async with HttpxAsyncBackend() as backend:
            client = MyAPI(base_url="...", backend=backend)
            result = await client.some_endpoint(request)

    Example with existing client:
        async with httpx.AsyncClient() as http_client:
            backend = HttpxAsyncBackend(client=http_client)
            client = MyAPI(base_url="...", backend=backend)
            result = await client.some_endpoint(request)
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """
        Initialize the backend.

        Args:
            client: Optional existing httpx.AsyncClient. If not provided,
                    a client will be created when entering the context manager.
        """
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> HttpxAsyncBackend:
        """Enter async context - creates client if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context - closes client if we created it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpxResponse:
        """
        Make an async HTTP request using httpx.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            content: Optional request body as bytes
            headers: Optional request headers
            timeout: Optional timeout in seconds

        Returns:
            HttpxResponse containing status, content, and headers

        Raises:
            RuntimeError: If called without entering context manager or providing client
        """
        if self._client is None:
            raise RuntimeError(
                "HttpxAsyncBackend requires a client. Either use 'async with HttpxAsyncBackend()' "
                "or pass an existing client to the constructor."
            )

        response = await self._client.request(
            method=method,
            url=url,
            content=content,
            headers=headers,
            timeout=timeout,
        )

        return HttpxResponse(
            status_code=response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )


# ---------------------------------------------------------------------------
# Sync Backend
# ---------------------------------------------------------------------------


class HttpxBackend:
    """
    Sync HTTP backend using httpx.

    Can be used as a context manager for automatic client management,
    or initialized with an existing client for more control.

    Example as context manager:
        with HttpxBackend() as backend:
            client = MyAPI(base_url="...", backend=backend)
            result = client.some_endpoint(request)

    Example with existing client:
        with httpx.Client() as http_client:
            backend = HttpxBackend(client=http_client)
            client = MyAPI(base_url="...", backend=backend)
            result = client.some_endpoint(request)
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        """
        Initialize the backend.

        Args:
            client: Optional existing httpx.Client. If not provided,
                    a client will be created when entering the context manager.
        """
        self._client = client
        self._owns_client = client is None

    def __enter__(self) -> HttpxBackend:
        """Enter context - creates client if needed."""
        if self._client is None:
            self._client = httpx.Client()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context - closes client if we created it."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpxResponse:
        """
        Make a sync HTTP request using httpx.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            content: Optional request body as bytes
            headers: Optional request headers
            timeout: Optional timeout in seconds

        Returns:
            HttpxResponse containing status, content, and headers

        Raises:
            RuntimeError: If called without entering context manager or providing client
        """
        if self._client is None:
            raise RuntimeError(
                "HttpxBackend requires a client. Either use 'with HttpxBackend()' "
                "or pass an existing client to the constructor."
            )

        response = self._client.request(
            method=method,
            url=url,
            content=content,
            headers=headers,
            timeout=timeout,
        )

        return HttpxResponse(
            status_code=response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )
