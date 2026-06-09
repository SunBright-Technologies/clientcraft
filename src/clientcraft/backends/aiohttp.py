"""
aiohttp backend implementation.

This module provides an async HTTP backend using the aiohttp library.
Requires: `pip install aiohttp` or `uv add "api-client[aiohttp]"`

Example usage:
    from clientcraft.backends import AiohttpBackend
    from clientcraft.async_client import AsyncAPIClient

    class UserAPI(AsyncAPIClient):
        get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]

    # Using as context manager (recommended - handles session lifecycle)
    async with AiohttpBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = await client.get_user(GetUserRequest(user_id="123"))

    # Using with existing session
    async with aiohttp.ClientSession() as session:
        backend = AiohttpBackend(session=session)
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = await client.get_user(GetUserRequest(user_id="123"))
"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType

try:
    import aiohttp
except ImportError as e:
    raise ImportError(
        "aiohttp is required for AiohttpBackend. "
        "Install it with: pip install aiohttp or uv add 'api-client[aiohttp]'"
    ) from e


@dataclass
class AiohttpResponse:
    """
    Wrapper around aiohttp.ClientResponse to satisfy HttpResponse protocol.

    aiohttp responses are async, so we need to read the content before
    returning. This dataclass stores the pre-read response data.
    """

    status_code: int
    content: bytes
    headers: dict[str, str]


class AiohttpBackend:
    """
    Async HTTP backend using aiohttp.

    Can be used as an async context manager for automatic session management,
    or initialized with an existing session for more control.

    Example as context manager:
        async with AiohttpBackend() as backend:
            client = MyAPI(base_url="...", backend=backend)
            result = await client.some_endpoint(request)

    Example with existing session:
        async with aiohttp.ClientSession() as session:
            backend = AiohttpBackend(session=session)
            client = MyAPI(base_url="...", backend=backend)
            result = await client.some_endpoint(request)
    """

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """
        Initialize the backend.

        Args:
            session: Optional existing aiohttp.ClientSession. If not provided,
                     a session will be created when entering the context manager.
        """
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> AiohttpBackend:
        """Enter async context - creates session if needed."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context - closes session if we created it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> AiohttpResponse:
        """
        Make an async HTTP request using aiohttp.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            content: Optional request body as bytes
            headers: Optional request headers
            timeout: Optional timeout in seconds

        Returns:
            AiohttpResponse containing status, content, and headers

        Raises:
            RuntimeError: If called without entering context manager or providing session
        """
        if self._session is None:
            raise RuntimeError(
                "AiohttpBackend requires a session. Either use 'async with AiohttpBackend()' "
                "or pass an existing session to the constructor."
            )

        # Build timeout config
        aiohttp_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None

        async with self._session.request(
            method=method,
            url=url,
            data=content,
            headers=headers,
            timeout=aiohttp_timeout,
        ) as response:
            # Read content while response is open
            response_content = await response.read()

            # Convert headers to dict (aiohttp uses CIMultiDictProxy)
            response_headers = dict(response.headers)

            return AiohttpResponse(
                status_code=response.status,
                content=response_content,
                headers=response_headers,
            )
