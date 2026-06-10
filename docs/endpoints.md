# Endpoints

An endpoint is a typed annotation on your client class:

```python
endpoint_name: Method[RequestModel, ResponseModel, Literal["/path"]]
```

- **`Method`** — one of the endpoint types below; it fixes the HTTP method and
  how the request is serialized.
- **`RequestModel`** — a Pydantic model (or `None` for
  [parameterless endpoints](parameterless-endpoints.md)).
- **`ResponseModel`** — a Pydantic model, a
  [response wrapper](requests-responses.md#response-types), or `None`.
- **`Literal["/path"]`** — the path template, optionally with `{placeholders}`.

## Endpoint types

| Sync     | Async         | HTTP Method | Request style | Typical use      |
|----------|---------------|-------------|---------------|------------------|
| `Get`    | `AsyncGet`    | GET         | Query params  | Read operations  |
| `Post`   | `AsyncPost`   | POST        | JSON body     | Create operations|
| `Put`    | `AsyncPut`    | PUT         | JSON body     | Full update      |
| `Patch`  | `AsyncPatch`  | PATCH       | JSON body     | Partial update   |
| `Delete` | `AsyncDelete` | DELETE      | Query params  | Delete operations|

The sync and async variants are interchangeable in shape — use the `Async*`
types on an `AsyncAPIClient`, the plain types on an `APIClient`.

## How the request model maps to the request

When you call an endpoint, the request model is dumped (with `exclude_none=True`)
and split into three destinations:

1. **Path parameters.** Any `{name}` placeholder in the path is filled from the
   field of the same name on the request model.
2. **Query string** (GET / DELETE). All remaining fields are URL-encoded onto the
   query string.
3. **JSON body** (POST / PUT / PATCH). All remaining fields are serialized into a
   JSON request body.

```python
class UpdateUserRequest(BaseModel):
    user_id: str       # -> path: /users/{user_id}
    name: str          # -> JSON body
    email: str         # -> JSON body


class UserAPI(APIClient):
    update_user: Put[UpdateUserRequest, User, Literal["/users/{user_id}"]]


client.update_user(UpdateUserRequest(user_id="7", name="Al", email="al@x.com"))
# PUT https://api.example.com/users/7   body: {"name": "Al", "email": "al@x.com"}
```

For a GET, the same leftover fields become query parameters instead:

```python
class SearchRequest(BaseModel):
    query: str
    limit: int | None = None


class UserAPI(APIClient):
    search_users: Get[SearchRequest, UserList, Literal["/users/search"]]


client.search_users(SearchRequest(query="ada", limit=10))
# GET https://api.example.com/users/search?query=ada&limit=10
```

!!! warning "Missing path parameters raise"
    If a `{placeholder}` in the path has no matching field in the request model
    (after `exclude_none`), preparation raises `ValueError`.

## Query value serialization

Query parameters are stringified with a small set of rules:

- `bool` → `"true"` / `"false"`
- `list` → comma-joined (`[1, 2, 3]` → `"1,2,3"`)
- everything else → `str(value)`

## What an endpoint returns

The return type is driven by the response model — see
[Requests & Responses](requests-responses.md). In short: a Pydantic model is
parsed and returned as that model; `TextResponse` / `BytesResponse` wrap raw
content; `None` means no body is expected and the call returns `None`.
