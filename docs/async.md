# Async Clients

clientcraft mirrors the sync API for asyncio. The declaration style is identical;
you swap three things:

| Sync                          | Async                                |
|-------------------------------|--------------------------------------|
| `APIClient`                   | `AsyncAPIClient`                     |
| `Get`, `Post`, ...            | `AsyncGet`, `AsyncPost`, ...         |
| a sync backend                | an async backend                     |

Calls become awaitables.

```python
from typing import Literal
from pydantic import BaseModel
from clientcraft import AsyncGet, AsyncPost
from clientcraft.async_client import AsyncAPIClient
from clientcraft.backends.aiohttp import AiohttpBackend


class GetUserRequest(BaseModel):
    user_id: str


class User(BaseModel):
    id: str
    name: str
    email: str


class AsyncUserAPI(AsyncAPIClient):
    get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]


async def main() -> None:
    async with AiohttpBackend() as backend:
        client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)
        user = await client.get_user(GetUserRequest(user_id="123"))
        print(user.name)
```

## Concurrency

Because each call is a coroutine, `asyncio.gather` fans out requests
concurrently over a single backend session:

```python
async with AiohttpBackend() as backend:
    client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)

    a, b, c = await asyncio.gather(
        client.get_user(GetUserRequest(user_id="1")),
        client.get_user(GetUserRequest(user_id="2")),
        client.get_user(GetUserRequest(user_id="3")),
    )
```

## Async backends

Two async backends ship with clientcraft:

- [`AiohttpBackend`](backends.md#aiohttpbackend) — requires `aiohttp`
- [`HttpxAsyncBackend`](backends.md#httpxbackend-httpxasyncbackend) — requires `httpx`

Both are async context managers; entering the `async with` block manages the
underlying session lifecycle. You can also pass an existing session/client into
the constructor if you manage its lifecycle yourself.
