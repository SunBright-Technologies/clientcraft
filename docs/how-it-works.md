# How It Works

clientcraft turns type annotations into working methods. This page explains the
machinery behind that — useful if you want to extend the library or debug
unexpected behavior.

## The annotation is the definition

When you write:

```python
class UserAPI(APIClient):
    get_user: Get[GetUserRequest, User, Literal["/users/{user_id}"]]
```

`Get[...]` is **not** a normal generic subscription at runtime. `Get` uses a
metaclass (`_EndpointTypeMeta`) whose `__getitem__` runs when you subscript it.
It:

1. unpacks the three parameters (request model, response model, path literal),
2. extracts the path string from the `Literal`,
3. infers the **response style** from the response model (`JSON` / `TEXT` /
   `BYTES` / `NONE`),
4. and returns an `Annotated[...]` type carrying an `EndpointInfo` dataclass
   (method, path, request style, response style).

So the annotation's *value* is an `Annotated` type with all the metadata baked in.

## `__init_subclass__` wires up descriptors

`BaseAPIClient.__init_subclass__` runs when you define a client subclass. It
calls `typing.get_type_hints(cls, include_extras=True)` to resolve every
annotation, then for each one that `extract_endpoint_info` recognizes as an
endpoint, it replaces the class attribute with an **endpoint descriptor**.

This is why clients must be defined where their request/response models are
importable — `get_type_hints` has to resolve the names.

## Descriptors create bound endpoints

The descriptor implements `__get__`. When you access `client.get_user`, the
descriptor returns a **bound endpoint** — a small callable object that holds the
client plus the endpoint's metadata. Calling it:

1. **prepares** a `PreparedRequest` (URL with path params interpolated, query
   string or JSON body, headers),
2. hands it to the client's **backend**,
3. **parses** the `HttpResponse` according to the response style (raising
   `HttpError` on status `>= 400`).

Sync and async clients share this flow; only the call/await step differs, so the
common logic lives in `BaseBoundEndpoint`.

## Why a `.pyi` stub?

Type checkers can't follow the runtime metaclass construction, so the package
ships hand-written stubs (`__init__.pyi`) describing the *static* view: `Get`,
`Post`, etc. as generics whose call returns the response model (and
`AsyncGet`/... returning a `Coroutine`). The stub also encodes the
[parameterless endpoint](parameterless-endpoints.md) overloads — when the request
type is `None`, the call takes no argument.

The result: one source of truth for behavior (the runtime) and one for types
(the stub), kept in agreement by the test suite.

## Data flow at a glance

```
Get[Req, Resp, "/path"]          # annotation
        │  _EndpointTypeMeta.__getitem__
        ▼
Annotated[Endpoint[Req, Resp], EndpointInfo(method, path, req_style, resp_style)]
        │  __init_subclass__ + extract_endpoint_info
        ▼
EndpointDescriptor                # set as the class attribute
        │  __get__(client)
        ▼
BoundEndpoint(client, info)       # callable
        │  __call__(request)
        ▼
prepare_request → backend.request → parse_response → Resp | None
```
