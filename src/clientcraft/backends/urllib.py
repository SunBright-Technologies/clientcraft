"""
urllib backend implementation.

This module provides a sync HTTP backend using Python's standard library urllib.
No additional dependencies required - works with any Python installation.

Example usage:
    from clientcraft.backends.urllib import UrllibBackend
    from clientcraft.client import APIClient

    class UserAPI(APIClient):
        get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]

    with UrllibBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = client.get_user(GetUserRequest(user_id="123"))

Note:
    urllib doesn't have a session concept like requests/httpx, so the context
    manager is provided for API consistency but doesn't manage any resources.
    For connection pooling, consider using requests or httpx instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class UrllibResponse:
    """
    Response wrapper to satisfy HttpResponse protocol.

    Converts urllib's HTTPResponse into a simple dataclass with
    the required status_code, content, and headers properties.
    """

    status_code: int
    content: bytes
    headers: dict[str, str]


class UrllibBackend:
    """
    Sync HTTP backend using Python's standard library urllib.

    This backend requires no external dependencies, making it useful for
    environments where installing packages is difficult or when you want
    to minimize dependencies.

    Can be used as a context manager for API consistency with other backends,
    though urllib doesn't maintain persistent connections.

    Example:
        with UrllibBackend() as backend:
            client = MyAPI(base_url="...", backend=backend)
            result = client.some_endpoint(request)

    Limitations:
        - No connection pooling (each request opens a new connection)
        - No automatic retry logic
        - Less feature-rich than requests/httpx

    Note:
        Some APIs block the default Python-urllib User-Agent. If you encounter
        403 errors, provide a custom User-Agent via the client's default_headers:

            client = MyAPI(
                base_url="...",
                backend=backend,
                default_headers={"User-Agent": "MyApp/1.0"}
            )

    For production use with high request volumes, consider using
    RequestsBackend or HttpxBackend instead.
    """

    def __init__(self, *, default_timeout: float | None = 30.0) -> None:
        """
        Initialize the backend.

        Args:
            default_timeout: Default timeout in seconds for requests.
                           Set to None for no timeout (not recommended).
        """
        self._default_timeout = default_timeout
        self._closed = False

    def __enter__(self) -> UrllibBackend:
        """Enter context - provided for API consistency."""
        self._closed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context - marks backend as closed."""
        self._closed = True

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> UrllibResponse:
        """
        Make a sync HTTP request using urllib.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            content: Optional request body as bytes
            headers: Optional request headers
            timeout: Optional timeout in seconds (uses default_timeout if not specified)

        Returns:
            UrllibResponse containing status, content, and headers

        Raises:
            RuntimeError: If called after the context manager has exited
            urllib.error.URLError: If the request fails (network error, etc.)
        """
        if self._closed:
            raise RuntimeError(
                "UrllibBackend has been closed. Use 'with UrllibBackend()' to ensure proper lifecycle management."
            )

        # Build the request
        req = Request(
            url=url,
            data=content,
            headers=headers or {},
            method=method,
        )

        # Determine timeout
        effective_timeout = timeout if timeout is not None else self._default_timeout

        try:
            # Make the request
            with urlopen(req, timeout=effective_timeout) as response:
                return UrllibResponse(
                    status_code=response.status,
                    content=response.read(),
                    headers=dict(response.headers),
                )
        except HTTPError as e:
            # HTTPError is raised for 4xx/5xx responses
            # We still want to return these as responses, not exceptions
            return UrllibResponse(
                status_code=e.code,
                content=e.read(),
                headers=dict(e.headers) if e.headers else {},
            )
        except URLError:
            # Re-raise network errors (DNS failure, connection refused, etc.)
            raise
