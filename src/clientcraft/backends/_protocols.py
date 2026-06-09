"""
Protocol definitions for HTTP backends.

These protocols define the interface that backend implementations must satisfy.
They use structural typing (Protocol), so any class with matching methods works.
"""

from __future__ import annotations

from typing import Protocol


class HttpResponse(Protocol):
    """
    Protocol for HTTP responses.

    Any object with these properties works - no inheritance required.
    Most HTTP libraries (requests, httpx, aiohttp) return responses that
    satisfy this protocol or can be easily adapted.
    """

    @property
    def status_code(self) -> int:
        """HTTP status code (e.g., 200, 404, 500)."""
        ...

    @property
    def content(self) -> bytes:
        """Raw response body as bytes."""
        ...

    @property
    def headers(self) -> dict[str, str]:
        """Response headers as a dictionary."""
        ...


class HttpBackend(Protocol):
    """
    Protocol for synchronous HTTP backends.

    Any object with a matching `request` method works - no inheritance required.
    This allows easy integration with requests, httpx, or custom implementations.

    Example with requests:
        class RequestsBackend:
            def __init__(self, session: requests.Session | None = None):
                self.session = session or requests.Session()

            def request(self, method, url, *, content=None, headers=None, timeout=None):
                resp = self.session.request(method, url, data=content, headers=headers, timeout=timeout)
                return resp  # requests.Response satisfies HttpResponse protocol
    """

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """
        Make a synchronous HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Full URL to request
            content: Optional request body as bytes
            headers: Optional request headers
            timeout: Optional timeout in seconds

        Returns:
            An object satisfying the HttpResponse protocol
        """
        ...


class AsyncHttpBackend(Protocol):
    """
    Protocol for asynchronous HTTP backends.

    Any object with a matching async `request` method works - no inheritance required.
    This allows easy integration with httpx.AsyncClient, aiohttp, or custom implementations.

    Example with httpx:
        class HttpxBackend:
            def __init__(self, client: httpx.AsyncClient | None = None):
                self.client = client or httpx.AsyncClient()

            async def request(self, method, url, *, content=None, headers=None, timeout=None):
                resp = await self.client.request(method, url, content=content, headers=headers, timeout=timeout)
                return resp  # httpx.Response satisfies HttpResponse protocol
    """

    async def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """
        Make an asynchronous HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Full URL to request
            content: Optional request body as bytes
            headers: Optional request headers
            timeout: Optional timeout in seconds

        Returns:
            An object satisfying the HttpResponse protocol
        """
        ...
