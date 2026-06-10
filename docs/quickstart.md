# Quick Start

This walks through defining and using a small client end to end.

## 1. Define your models

Requests and responses are plain Pydantic models.

```python
from pydantic import BaseModel


class GetUserRequest(BaseModel):
    user_id: str


class CreateUserRequest(BaseModel):
    name: str
    email: str


class DeleteUserRequest(BaseModel):
    user_id: str


class User(BaseModel):
    id: str
    name: str
    email: str
```

## 2. Declare the API

Subclass `APIClient` and annotate each endpoint. The annotation carries
everything: the request model, the response model, and the path.

```python
from typing import Literal
from clientcraft import Get, Post, Delete
from clientcraft.client import APIClient


class UserAPI(APIClient):
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
    create_user: Post[CreateUserRequest, User, Literal["/users"]]
    delete_user: Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]
```

!!! note "Declare clients at module level"
    clientcraft resolves the annotations with `typing.get_type_hints`, so the
    request/response models must be importable from the client's module scope.
    Defining everything at module level (not inside a function) keeps this simple.

## 3. Pick a backend and call

Concrete backends are imported from their submodule (see [Backends](backends.md)):

```python
from clientcraft.backends.requests import RequestsBackend

backend = RequestsBackend()
client = UserAPI(base_url="https://api.example.com", backend=backend)

# Fully typed — get_user returns a User
user = client.get_user(GetUserRequest(user_id="123"))
print(user.name)

new_user = client.create_user(
    CreateUserRequest(name="Alice", email="alice@example.com")
)

# None response type -> returns None
client.delete_user(DeleteUserRequest(user_id="123"))
```

## Default headers and timeout

Both are set on the client and applied to every request:

```python
client = UserAPI(
    base_url="https://api.example.com",
    backend=backend,
    default_headers={"Authorization": "Bearer <token>"},
    default_timeout=30.0,
)
```

## Going async

The same shape works with `AsyncAPIClient` and an async backend — see
[Async Clients](async.md).

```python
from clientcraft import AsyncGet
from clientcraft.async_client import AsyncAPIClient
from clientcraft.backends.aiohttp import AiohttpBackend


class AsyncUserAPI(AsyncAPIClient):
    get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]


async with AiohttpBackend() as backend:
    client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)
    user = await client.get_user(GetUserRequest(user_id="123"))
```
