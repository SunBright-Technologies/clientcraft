# Declarative API Client

A declarative, type-safe API client framework for Python 3.12+.

## Features

- **Declarative endpoint definitions** using type annotations
- **Type-safe** request and response handling with Pydantic
- **Sync and async** client support
- **Pluggable backends** (aiohttp, httpx, or custom)
- **Multiple response types**: JSON, text, bytes, or no content

## Installation

```bash
# Using uv
uv add clientcraft

# With aiohttp backend
uv add "clientcraft[aiohttp]"

# With all optional backends
uv add "clientcraft[all]"
```

## Quick Start

### Define your API

```python
from typing import Literal
from pydantic import BaseModel
from clientcraft import Get, Post, Delete
from clientcraft.client import APIClient

# Define request/response models
class GetUserRequest(BaseModel):
    user_id: str

class User(BaseModel):
    id: str
    name: str
    email: str

class CreateUserRequest(BaseModel):
    name: str
    email: str

# Define your API client declaratively
class UserAPI(APIClient):
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
    create_user: Post[CreateUserRequest, User, Literal["/users"]]
    delete_user: Delete[GetUserRequest, None, Literal["/users/{user_id}"]]
```

### Use your API

```python
from clientcraft.backends import RequestsBackend

# Create client with a backend
backend = RequestsBackend()
client = UserAPI(base_url="https://api.example.com", backend=backend)

# Make requests - fully typed!
user = client.get_user(GetUserRequest(user_id="123"))
print(user.name)  # Type checker knows this is a User

# Create a user
new_user = client.create_user(CreateUserRequest(name="Alice", email="alice@example.com"))
```

### Async Usage

```python
from clientcraft import AsyncGet, AsyncPost
from clientcraft.async_client import AsyncAPIClient
from clientcraft.backends import AiohttpBackend

class AsyncUserAPI(AsyncAPIClient):
    get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]
    create_user: AsyncPost[CreateUserRequest, User, Literal["/users"]]

async with AiohttpBackend() as backend:
    client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)
    user = await client.get_user(GetUserRequest(user_id="123"))
```

## Endpoint Types

| Type | HTTP Method | Request Style | Description |
|------|-------------|---------------|-------------|
| `Get` | GET | Query params | Read operations |
| `Post` | POST | JSON body | Create operations |
| `Put` | PUT | JSON body | Full update |
| `Patch` | PATCH | JSON body | Partial update |
| `Delete` | DELETE | Query params | Delete operations |

## Response Types

```python
from clientcraft import TextResponse, BytesResponse

class HealthAPI(APIClient):
    # JSON response (default)
    get_user: Get[Request, User, Literal["/users/{id}"]]
    
    # Text response
    health_check: Get[Request, TextResponse, Literal["/health"]]
    
    # Binary response
    download: Get[Request, BytesResponse, Literal["/files/{id}"]]
    
    # No response body (204 No Content)
    delete_user: Delete[Request, None, Literal["/users/{id}"]]
```

## Development

```bash
# Clone and setup
cd clientcraft
uv sync --all-extras

# Run tests
uv run pytest

# Type checking
uv run mypy

# Linting
uv run ruff check .
```

## License

MIT
