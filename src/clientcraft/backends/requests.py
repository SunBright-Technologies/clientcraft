"""
requests backend implementation.

This module provides a sync HTTP backend using the requests library.
Requires: `pip install requests` or `uv add "api-client[requests]"`

Example usage:
    from clientcraft.backends.requests import RequestsBackend
    from clientcraft.client import APIClient

    class UserAPI(APIClient):
        get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]

    # Using as context manager (recommended - handles session lifecycle)
    with RequestsBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = client.get_user(GetUserRequest(user_id="123"))

    # Using with existing session
    with requests.Session() as session:
        backend = RequestsBackend(session=session)
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = client.get_user(GetUserRequest(user_id="123"))
"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType

try:
    import requests
except ImportError as e:
    raise ImportError(
        "requests is required for RequestsBackend. "
        "Install it with: pip install requests or uv add 'api-client[requests]'"
    ) from e


@dataclass
class RequestsResponse:
    """
    Wrapper around requests.Response to satisfy HttpResponse protocol.

    While requests.Response has status_code and content, its headers
    are a CaseInsensitiveDict, so we normalize them to a plain dict.
    """

    status_code: int
    content: bytes
    headers: dict[str, str]


class RequestsBackend:
    """
    Sync HTTP backend using requests.

    Can be used as a context manager for automatic session management,
    or initialized with an existing session for more control.

    Example as context manager:
        with RequestsBackend() as backend:
            client = MyAPI(base_url="...", backend=backend)
            result = client.some_endpoint(request)

    Example with existing session:
        with requests.Session() as session:
            backend = RequestsBackend(session=session)
            client = MyAPI(base_url="...", backend=backend)
            result = client.some_endpoint(request)
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        """
        Initialize the backend.

        Args:
            session: Optional existing requests.Session. If not provided,
                     a session will be created when entering the context manager.
        """
        self._session = session
        self._owns_session = session is None

    def __enter__(self) -> RequestsBackend:
        """Enter context - creates session if needed."""
        if self._session is None:
            self._session = requests.Session()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context - closes session if we created it."""
        if self._owns_session and self._session is not None:
            self._session.close()
            self._session = None

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> RequestsResponse:
        """
        Make a sync HTTP request using requests.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            content: Optional request body as bytes
            headers: Optional request headers
            timeout: Optional timeout in seconds

        Returns:
            RequestsResponse containing status, content, and headers

        Raises:
            RuntimeError: If called without entering context manager or providing session
        """
        if self._session is None:
            raise RuntimeError(
                "RequestsBackend requires a session. Either use 'with RequestsBackend()' "
                "or pass an existing session to the constructor."
            )

        response = self._session.request(
            method=method,
            url=url,
            data=content,
            headers=headers,
            timeout=timeout,
        )

        return RequestsResponse(
            status_code=response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )
