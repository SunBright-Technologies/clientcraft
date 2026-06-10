# Backends

A **backend** is the object that actually performs the HTTP request. clientcraft
is backend-agnostic: the client builds a `PreparedRequest`, hands it to the
backend, and parses whatever `HttpResponse` comes back.

!!! important "Import concrete backends from their submodule"
    `clientcraft.backends` exposes only the **protocols** (`HttpBackend`,
    `AsyncHttpBackend`, `HttpResponse`). The concrete backend classes each live
    in their own submodule and must be imported from there:

    ```python
    from clientcraft.backends.urllib import UrllibBackend
    from clientcraft.backends.requests import RequestsBackend
    from clientcraft.backends.httpx import HttpxBackend, HttpxAsyncBackend
    from clientcraft.backends.aiohttp import AiohttpBackend
    ```

## Available backends

| Backend             | Module                          | Sync/Async | Requires    |
|---------------------|---------------------------------|------------|-------------|
| `UrllibBackend`     | `clientcraft.backends.urllib`   | Sync       | — (stdlib)  |
| `RequestsBackend`   | `clientcraft.backends.requests` | Sync       | `requests`  |
| `HttpxBackend`      | `clientcraft.backends.httpx`    | Sync       | `httpx`     |
| `HttpxAsyncBackend` | `clientcraft.backends.httpx`    | Async      | `httpx`     |
| `AiohttpBackend`    | `clientcraft.backends.aiohttp`  | Async      | `aiohttp`   |

### UrllibBackend

Standard-library backend — zero third-party dependencies. Good for scripts and
environments where you can't add packages.

```python
from clientcraft.backends.urllib import UrllibBackend

with UrllibBackend(default_timeout=30.0) as backend:
    client = UserAPI(base_url="https://api.example.com", backend=backend)
    user = client.get_user(GetUserRequest(user_id="123"))
```

### RequestsBackend

Backed by the popular `requests` library. Accepts an optional pre-configured
`requests.Session`.

```python
from clientcraft.backends.requests import RequestsBackend

backend = RequestsBackend()                 # or RequestsBackend(session=my_session)
client = UserAPI(base_url="https://api.example.com", backend=backend)
```

### HttpxBackend / HttpxAsyncBackend

Sync and async backends on top of `httpx`. Each accepts an optional existing
`httpx.Client` / `httpx.AsyncClient`.

```python
from clientcraft.backends.httpx import HttpxBackend, HttpxAsyncBackend

with HttpxBackend() as backend:
    client = UserAPI(base_url="https://api.example.com", backend=backend)

async with HttpxAsyncBackend() as backend:
    aclient = AsyncUserAPI(base_url="https://api.example.com", backend=backend)
```

### AiohttpBackend

Async backend on top of `aiohttp`. Accepts an optional existing
`aiohttp.ClientSession`.

```python
from clientcraft.backends.aiohttp import AiohttpBackend

async with AiohttpBackend() as backend:
    client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)
```

## Choosing a backend

- **No dependencies / scripts** → `UrllibBackend`
- **Existing requests-based codebase** → `RequestsBackend`
- **Modern sync or async with one library** → `httpx` backends
- **High-concurrency asyncio** → `AiohttpBackend`

Want something else (a test double, a caching layer, a custom transport)? See
[Custom Backends](custom-backends.md).
