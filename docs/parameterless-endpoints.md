# Parameterless Endpoints

Some endpoints take no input at all — a health check, a "list everything"
collection route, a "current user" lookup driven entirely by an auth header.

For these, declare the **request type as `None`**:

```python
from typing import Literal
from clientcraft import Get
from clientcraft.client import APIClient


class StatusAPI(APIClient):
    list_users: Get[None, UserList, Literal["/users"]]
    ping: Get[None, TextResponse, Literal["/ping"]]
```

## Calling them

A parameterless endpoint can be called with **no argument**, or with an explicit
`None` — they behave identically:

```python
client = StatusAPI(base_url="https://api.example.com", backend=backend)

users = client.list_users()       # no argument
users = client.list_users(None)   # explicit None — equivalent
```

No query string and no body are sent. Path parameters are not allowed on a
parameterless endpoint (there is no request model to fill them from).

## Async

The same works with the `Async*` types:

```python
from clientcraft import AsyncGet
from clientcraft.async_client import AsyncAPIClient


class AsyncStatusAPI(AsyncAPIClient):
    list_users: AsyncGet[None, UserList, Literal["/users"]]


users = await client.list_users()
```

## Type checking

The bundled type stubs make this fully type-safe. When the request type is
`None`, the call signature accepts zero arguments (or `None`); for any other
request type the argument remains required:

```python
client.list_users()        # ok
client.list_users(None)     # ok
client.get_user()           # type error: missing request argument
```
