# Requests & Responses

## Request styles

Each endpoint type fixes a **request style** that decides where non-path fields go:

| Request style      | Endpoint types        | Destination          |
|--------------------|-----------------------|----------------------|
| `RequestStyle.QUERY` | `Get`, `Delete`     | URL query string     |
| `RequestStyle.BODY`  | `Post`, `Put`, `Patch` | JSON request body |

Requests are dumped with `exclude_none=True`, so optional fields left as `None`
are omitted from the query string / body entirely.

## Response types

The **response model** (the second type parameter) controls how the HTTP
response is turned into a Python value:

| Response model       | Response style        | Call returns                          |
|----------------------|-----------------------|---------------------------------------|
| A Pydantic model     | `ResponseStyle.JSON`  | An instance of that model             |
| `TextResponse`       | `ResponseStyle.TEXT`  | `TextResponse(content=<str>)`         |
| `BytesResponse`      | `ResponseStyle.BYTES` | `BytesResponse(content=<bytes>)`      |
| `None`               | `ResponseStyle.NONE`  | `None`                                |

```python
from typing import Literal
from clientcraft import Get, Delete, TextResponse, BytesResponse
from clientcraft.client import APIClient


class FilesAPI(APIClient):
    # JSON (default) — body parsed into the Pydantic model
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]

    # Plain text
    health_check: Get[None, TextResponse, Literal["/health"]]

    # Raw bytes
    download: Get[GetFileRequest, BytesResponse, Literal["/files/{file_id}"]]

    # No body expected (e.g. 204) — returns None
    delete_user: Delete[DeleteUserRequest, None, Literal["/users/{user_id}"]]
```

### Text and bytes wrappers

`TextResponse` and `BytesResponse` are tiny Pydantic models with a single
`content` field. They exist so every response — JSON or not — flows through the
same typed machinery.

```python
result = client.health_check()
assert isinstance(result, TextResponse)
print(result.content)  # the response body as str
```

### Empty JSON bodies

For a JSON response model, an empty response body is handled gracefully: the
model is validated against `{}`. If the model has required fields this raises a
Pydantic `ValidationError` (which is the correct signal that the server returned
nothing usable).

## Headers

`Content-Type: application/json` and `Accept: application/json` are sent by
default, merged with any `default_headers` you pass to the client. On success
the parsed value is returned; response headers are currently surfaced only on
errors (see [Error Handling](error-handling.md)).
