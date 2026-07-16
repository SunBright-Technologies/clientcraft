# clientcraft

A declarative, type-safe API client framework for Python 3.12+.

Define your HTTP API as a class of typed annotations and get fully-typed,
Pydantic-validated request/response handling for free — no boilerplate per
endpoint.

📖 **Full documentation:** https://sunbright-technologies.github.io/clientcraft/

## Features

- **Declarative endpoint definitions** using type annotations
- **Type-safe** request and response handling with Pydantic
- **Sync and async** client support
- **Pluggable backends**: urllib (no deps), requests, httpx, aiohttp, or custom
- **Multiple response types**: JSON, text, bytes, or no content
- **Parameterless endpoints**: declare `Get[None, ...]` for endpoints that take no request
- **Declarative error handling**: map HTTP errors to domain exceptions per endpoint or client-wide
- **Testing helpers**: a fake backend and client stubs to test both sides without the network

## Installation

```bash
# Using uv (urllib backend works with no extra dependencies)
uv add clientcraft

# With a specific backend
uv add "clientcraft[requests]"
uv add "clientcraft[httpx]"
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

class DeleteUserRequest(BaseModel):
    user_id: str

# Define your API client declaratively
class UserAPI(APIClient):
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
    create_user: Post[CreateUserRequest, User, Literal["/users"]]
    delete_user: Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]
```

### Use your API

Concrete backends live in their own submodules and must be imported from there
(`clientcraft.backends` itself only exposes the protocols):

```python
from clientcraft.backends.requests import RequestsBackend

# Create client with a backend
backend = RequestsBackend()
client = UserAPI(base_url="https://api.example.com", backend=backend)

# Make requests - fully typed!
user = client.get_user(GetUserRequest(user_id="123"))
print(user.name)  # Type checker knows this is a User

# Create a user
new_user = client.create_user(CreateUserRequest(name="Alice", email="alice@example.com"))
```

The standard-library `UrllibBackend` requires no third-party dependencies:

```python
from clientcraft.backends.urllib import UrllibBackend

with UrllibBackend() as backend:
    client = UserAPI(base_url="https://api.example.com", backend=backend)
    user = client.get_user(GetUserRequest(user_id="123"))
```

### Async Usage

```python
from typing import Literal
from clientcraft import AsyncGet, AsyncPost
from clientcraft.async_client import AsyncAPIClient
from clientcraft.backends.aiohttp import AiohttpBackend

class AsyncUserAPI(AsyncAPIClient):
    get_user: AsyncGet[GetUserRequest, User, Literal["/users/{user_id}"]]
    create_user: AsyncPost[CreateUserRequest, User, Literal["/users"]]

async with AiohttpBackend() as backend:
    client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)
    user = await client.get_user(GetUserRequest(user_id="123"))
```

## Endpoint Types

| Sync     | Async         | HTTP Method | Request Style | Description      |
|----------|---------------|-------------|---------------|------------------|
| `Get`    | `AsyncGet`    | GET         | Query params  | Read operations  |
| `Post`   | `AsyncPost`   | POST        | JSON body     | Create operations|
| `Put`    | `AsyncPut`    | PUT         | JSON body     | Full update      |
| `Patch`  | `AsyncPatch`  | PATCH       | JSON body     | Partial update   |
| `Delete` | `AsyncDelete` | DELETE      | Query params  | Delete operations|

Each is parameterized as `Endpoint[RequestModel, ResponseModel, Literal["/path"]]`.
Path parameters (`{user_id}`) are pulled from the request model; remaining fields
become the query string (GET/DELETE) or JSON body (POST/PUT/PATCH).

## Parameterless Endpoints

For endpoints that take no parameters at all, declare the request type as `None`.
The endpoint can then be called with no argument (or an explicit `None`):

```python
from typing import Literal
from clientcraft import Get
from clientcraft.client import APIClient

class StatusAPI(APIClient):
    list_users: Get[None, UserList, Literal["/users"]]

client = StatusAPI(base_url="https://api.example.com", backend=backend)

users = client.list_users()       # no argument
users = client.list_users(None)   # explicit None — equivalent
```

## Response Types

```python
from typing import Literal
from clientcraft import Get, Delete, TextResponse, BytesResponse

class FilesAPI(APIClient):
    # JSON response (default) — parsed into the Pydantic model
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]

    # Text response — returned as TextResponse(content=...)
    health_check: Get[None, TextResponse, Literal["/health"]]

    # Binary response — returned as BytesResponse(content=...)
    download: Get[GetFileRequest, BytesResponse, Literal["/files/{file_id}"]]

    # No response body (e.g. 204 No Content) — returns None
    delete_user: Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]
```

## Error Handling

By default any response with status `>= 400` raises `HttpError`. Opt into your own
domain exceptions declaratively — no `try/except` on status codes at every call
site:

```python
from typing import Annotated, Literal
from clientcraft import DEFAULT, DomainError, ErrorMap, Get, Raises
from clientcraft.client import APIClient

class UserNotFound(DomainError): ...
class RateLimited(DomainError): ...
class ApiError(DomainError): ...

class UserAPI(APIClient):
    get_user: Annotated[
        Get[GetUserRequest, User, Literal["/users/{user_id}"]],
        Raises(404, UserNotFound),                    # per-endpoint
    ]
    errors = ErrorMap({429: RateLimited, DEFAULT: ApiError})   # client-wide + catch-all
```

Resolution order: per-endpoint `Raises` → client `errors` → `handle_error`
(override for full control). An exception needing the response body can parse it in
`DomainError.from_http_error`. See the
[error handling guide](https://sunbright-technologies.github.io/clientcraft/error-handling/)
and [`examples/error_handling.py`](examples/error_handling.py).

## Testing

`clientcraft.testing` fakes either side of the client — no live server needed.

**Test your client** with `FakeBackend`: fake the transport, run the real client
(serialization, parsing, and error handling all run). Routes are backed by
`unittest.mock.Mock`s:

```python
from clientcraft.testing import FakeBackend

backend = FakeBackend()
with backend.mock_get("/users/1", json={"id": "1", "name": "Ada"}) as m:
    client = UserAPI(base_url="https://api.example.com", backend=backend)
    assert client.get_user(GetUserRequest(user_id="1")).name == "Ada"
    m.assert_called_once()
```

**Test code that uses your client** with `mock_client`: inject a stubbed client
whose endpoints are mocks (no backend needed):

```python
from clientcraft.testing import mock_client, mock_of

client = mock_client(UserAPI, get_user=User(id="1", name="Ada"))
# inject `client` into your service, exercise it, then:
mock_of(client, "get_user").assert_called_once_with(GetUserRequest(user_id="1"))
```

See the [testing guide](https://sunbright-technologies.github.io/clientcraft/testing/)
and [`examples/testing_your_client.py`](examples/testing_your_client.py) /
[`examples/testing_your_app.py`](examples/testing_your_app.py).

## Backends

| Backend             | Module                          | Sync/Async | Extra        |
|---------------------|---------------------------------|------------|--------------|
| `UrllibBackend`     | `clientcraft.backends.urllib`   | Sync       | none (stdlib)|
| `RequestsBackend`   | `clientcraft.backends.requests` | Sync       | `requests`   |
| `HttpxBackend`      | `clientcraft.backends.httpx`    | Sync       | `httpx`      |
| `HttpxAsyncBackend` | `clientcraft.backends.httpx`    | Async      | `httpx`      |
| `AiohttpBackend`    | `clientcraft.backends.aiohttp`  | Async      | `aiohttp`    |

Backends are protocol-based — any object implementing the `HttpBackend` /
`AsyncHttpBackend` protocol works, so you can supply your own.

## Examples

Runnable examples live in [`examples/`](examples/):

| File | Shows |
| --- | --- |
| [`basic_usage.py`](examples/basic_usage.py) | A declarative async client against the live PokeAPI |
| [`error_handling.py`](examples/error_handling.py) | HTTP errors → domain exceptions |
| [`testing_your_client.py`](examples/testing_your_client.py) | Testing a client with `FakeBackend` |
| [`testing_your_app.py`](examples/testing_your_app.py) | Testing app code with `mock_client` |

## Development

```bash
# Clone and setup
cd clientcraft
uv sync --all-extras

# Run tests
uv run pytest

# Type checking
uv run mypy src tests examples

# Linting and formatting
uv run ruff check src tests examples
uv run ruff format --check src tests examples
```

## License

MIT
