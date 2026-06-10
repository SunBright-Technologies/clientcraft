# clientcraft

A **declarative, type-safe API client framework** for Python 3.12+.

Describe an HTTP API as a class of typed annotations and clientcraft gives you a
fully-typed, Pydantic-validated client — no per-endpoint boilerplate.

```python
from typing import Literal
from pydantic import BaseModel
from clientcraft import Get, Post
from clientcraft.client import APIClient
from clientcraft.backends.requests import RequestsBackend


class GetUserRequest(BaseModel):
    user_id: str


class User(BaseModel):
    id: str
    name: str
    email: str


class UserAPI(APIClient):
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]


client = UserAPI(base_url="https://api.example.com", backend=RequestsBackend())
user = client.get_user(GetUserRequest(user_id="123"))  # -> User
print(user.name)
```

## Why clientcraft?

- **Declarative.** Endpoints are type annotations, not functions you write by hand.
- **Type-safe end to end.** The request model, the path, and the response model
  are all part of the type. Your type checker knows `get_user(...)` returns a `User`.
- **Pydantic validation.** Requests are serialized and responses are validated
  with Pydantic v2 models.
- **Sync and async.** Identical declarative style for both — pick `APIClient` or
  `AsyncAPIClient`.
- **Pluggable backends.** Ship with urllib (stdlib, no deps), requests, httpx,
  and aiohttp — or bring your own via a small protocol.
  
## Where to next

<div class="grid cards" markdown>

- :material-download: **[Installation](installation.md)** — install the package and a backend
- :material-rocket-launch: **[Quick Start](quickstart.md)** — a full working example
- :material-book-open-variant: **[Endpoints](endpoints.md)** — the endpoint types and how paths map to requests
- :material-cog: **[How It Works](how-it-works.md)** — the descriptor / metaclass design

</div>
