"""
HTTP Backend implementations for the API client.

This module provides both protocols (for structural typing) and concrete implementations.

Protocols:
    - HttpBackend: Sync backend protocol
    - AsyncHttpBackend: Async backend protocol
    - HttpResponse: Response protocol that backends must return

Implementations (import directly from submodules):
    - UrllibBackend: from clientcraft.backends.urllib import UrllibBackend
      (standard library, no dependencies)

    - RequestsBackend: from clientcraft.backends.requests import RequestsBackend
      (requires `requests` package)

    - HttpxBackend: from clientcraft.backends.httpx import HttpxBackend
    - HttpxAsyncBackend: from clientcraft.backends.httpx import HttpxAsyncBackend
      (requires `httpx` package)

    - AiohttpBackend: from clientcraft.backends.aiohttp import AiohttpBackend
      (requires `aiohttp` package)

For testing, a fake backend lives in its own namespace (not here, since it is not
a production backend): from clientcraft.testing import FakeBackend / FakeAsyncBackend.

Example usage with urllib (no dependencies):
    from clientcraft.backends.urllib import UrllibBackend
    from clientcraft.client import APIClient

    class UserAPI(APIClient):
        get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]

    with UrllibBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = client.get_user(GetUserRequest(user_id="123"))

Example usage with aiohttp (async):
    from clientcraft.backends.aiohttp import AiohttpBackend
    from clientcraft.async_client import AsyncAPIClient

    class UserAPI(AsyncAPIClient):
        get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]

    async with AiohttpBackend() as backend:
        client = UserAPI(base_url="https://api.example.com", backend=backend)
        user = await client.get_user(GetUserRequest(user_id="123"))
"""

from ._protocols import AsyncHttpBackend, HttpBackend, HttpResponse

__all__ = [
    # Protocols
    "HttpBackend",
    "AsyncHttpBackend",
    "HttpResponse",
]
