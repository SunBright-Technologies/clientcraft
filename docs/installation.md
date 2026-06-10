# Installation

clientcraft requires **Python 3.12+** and depends only on **Pydantic v2**.

The core package works out of the box with the standard-library
[`UrllibBackend`](backends.md#urllibbackend) — no third-party HTTP library
required. Other backends are opt-in via extras.

## With uv

```bash
# Core only (urllib backend available, no extra deps)
uv add clientcraft

# Pick a backend
uv add "clientcraft[requests]"
uv add "clientcraft[httpx]"
uv add "clientcraft[aiohttp]"

# Everything
uv add "clientcraft[all]"
```

## With pip

```bash
pip install clientcraft
pip install "clientcraft[requests]"
pip install "clientcraft[all]"
```

## Extras

| Extra        | Pulls in            | Backends enabled                       |
|--------------|---------------------|----------------------------------------|
| _(none)_     | `pydantic`          | `UrllibBackend`                        |
| `requests`   | `requests`          | `RequestsBackend`                      |
| `httpx`      | `httpx`             | `HttpxBackend`, `HttpxAsyncBackend`    |
| `aiohttp`    | `aiohttp`           | `AiohttpBackend`                       |
| `all`        | all of the above    | all backends                           |

See [Backends](backends.md) for details on each.
