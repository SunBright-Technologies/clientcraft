"""
Testing helpers: an in-memory fake backend whose routes are backed by mocks.

``FakeBackend`` (sync) and ``FakeAsyncBackend`` (async) let you test a client
subclass without the network. You register a response for a route with a
context manager that **yields a ``unittest.mock.Mock``**, so you get the full
mock toolbox — ``return_value``, ``side_effect``, ``wraps`` — and per-route call
inspection (``m.assert_called_once()``, ``m.call_args``).

Registrations are a **stack**: the most recently entered one wins, and leaving
its ``with`` block pops it, restoring whatever was registered before. That makes
fixtures compose cleanly — a test can override a fixture's response for the
duration of a block.

Example::

    from clientcraft.testing import FakeBackend

    def test_get_user():
        backend = FakeBackend()
        with backend.mock_get("/users/123", json={"id": "123", "name": "Ada"}) as m:
            client = UserAPI(base_url="https://api.example.com", backend=backend)

            user = client.get_user(GetUserRequest(user_id="123"))

            assert user.name == "Ada"
            m.assert_called_once()
            assert m.call_args.args[0].json() is None  # GET has no body
"""

from __future__ import annotations

import json as _json
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import Mock

from pydantic import BaseModel

from ._base import BaseAPIClient, EndpointDescriptor


@dataclass
class FakeResponse:
    """A canned response satisfying the ``HttpResponse`` protocol."""

    status_code: int
    content: bytes
    headers: dict[str, str]


@dataclass
class RecordedRequest:
    """The request passed to a route's mock, for assertions."""

    method: str
    url: str
    content: bytes | None
    headers: dict[str, str]

    def json(self) -> Any:
        """Parse the request body as JSON, or ``None`` if there is no body."""
        return None if self.content is None else _json.loads(self.content)


def _build_response(
    *,
    status: int,
    json: Any | None,
    text: str | None,
    content: bytes | None,
    headers: dict[str, str] | None,
) -> FakeResponse:
    """Turn the convenience kwargs into a concrete ``FakeResponse``."""
    provided = [x for x in (json, text, content) if x is not None]
    if len(provided) > 1:
        raise ValueError("Provide at most one of json=, text=, content=")

    hdrs = dict(headers or {})
    body: bytes
    if json is not None:
        body = json.model_dump_json().encode() if isinstance(json, BaseModel) else _json.dumps(json).encode()
        hdrs.setdefault("Content-Type", "application/json")
    elif text is not None:
        body = text.encode()
    elif content is not None:
        body = content
    else:
        body = b""

    return FakeResponse(status_code=status, content=body, headers=hdrs)


@dataclass
class _Route:
    method: str | None
    url: str | None
    mock: Mock

    def matches(self, request: RecordedRequest) -> bool:
        if self.method is not None and self.method.upper() != request.method.upper():
            return False
        return not (self.url is not None and self.url not in request.url)


class _FakeBackendBase:
    """Shared route stack, registration, and dispatch for the fake backends."""

    def __init__(self) -> None:
        self._routes: list[_Route] = []

    @contextmanager
    def mock(
        self,
        method: str | None = None,
        url: str | None = None,
        *,
        response: FakeResponse | None = None,
        status: int = 200,
        json: Any | None = None,
        text: str | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Iterator[Mock]:
        """Register a route for the duration of the ``with`` block, yielding its mock.

        Matching is by ``method`` (any if ``None``) and ``url`` (substring match;
        any if ``None``). The mock's ``return_value`` is the response; override
        ``return_value`` / ``side_effect`` on the yielded mock for dynamic
        behavior (sequences, raising to simulate a transport error). The route is
        pushed on a stack — it overrides any earlier match while active and is
        popped on exit, restoring the previous registration.
        """
        resp = (
            response
            if response is not None
            else _build_response(status=status, json=json, text=text, content=content, headers=headers)
        )
        m = Mock(name=f"{method or 'ANY'} {url or '*'}", return_value=resp)
        route = _Route(method=method, url=url, mock=m)
        self._routes.append(route)
        try:
            yield m
        finally:
            self._routes.remove(route)

    def mock_get(self, url: str | None = None, **kwargs: Any) -> AbstractContextManager[Mock]:
        return self.mock("GET", url, **kwargs)

    def mock_post(self, url: str | None = None, **kwargs: Any) -> AbstractContextManager[Mock]:
        return self.mock("POST", url, **kwargs)

    def mock_put(self, url: str | None = None, **kwargs: Any) -> AbstractContextManager[Mock]:
        return self.mock("PUT", url, **kwargs)

    def mock_patch(self, url: str | None = None, **kwargs: Any) -> AbstractContextManager[Mock]:
        return self.mock("PATCH", url, **kwargs)

    def mock_delete(self, url: str | None = None, **kwargs: Any) -> AbstractContextManager[Mock]:
        return self.mock("DELETE", url, **kwargs)

    def _resolve(
        self,
        method: str,
        url: str,
        content: bytes | None,
        headers: dict[str, str] | None,
    ) -> FakeResponse:
        request = RecordedRequest(method=method, url=url, content=content, headers=dict(headers or {}))
        # Newest registration wins (stack / LIFO), so overrides take effect.
        for route in reversed(self._routes):
            if route.matches(request):
                result: FakeResponse = route.mock(request)
                return result
        raise AssertionError(
            f"No mock registered for {method} {url}. "
            f"Active routes: {[(r.method, r.url) for r in self._routes] or 'none'}. "
            f"Register one with backend.mock_get(...) / backend.mock(...)."
        )


class FakeBackend(_FakeBackendBase):
    """Synchronous fake backend. See module docstring for usage."""

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        return self._resolve(method, url, content, headers)


class FakeAsyncBackend(_FakeBackendBase):
    """Asynchronous fake backend. Same API as ``FakeBackend`` with ``await``."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        return self._resolve(method, url, content, headers)


# ---------------------------------------------------------------------------
# Mocking a whole client (for code that depends on a client as a collaborator)
# ---------------------------------------------------------------------------


def _endpoint_names(cls: type) -> set[str]:
    """All endpoint attribute names declared on ``cls`` or its bases."""
    names: set[str] = set()
    for klass in cls.__mro__:
        for name, value in vars(klass).items():
            if isinstance(value, EndpointDescriptor):
                names.add(name)
    return names


def mock_client[C: BaseAPIClient[Any]](
    cls: type[C],
    /,
    *,
    base_url: str = "mock://test",
    **returns: Any,
) -> C:
    """Build a client instance whose endpoints are mocks, for injecting into tests.

    Unlike patching a live client, this needs no real backend — pass canned
    return values per endpoint by name::

        client = mock_client(UserAPI, get_user=User(id="1", name="Ada"))
        service = MyService(client)
        service.run()
        mock_of(client, "get_user").assert_called_once()

    Each keyword sets that endpoint mock's ``return_value``; pass a ``Mock`` to
    supply your own (e.g. with ``side_effect``). Only named endpoints are mocked —
    calling an unmocked endpoint raises loudly, so forgotten stubs surface.
    """
    instance = cls(base_url=base_url, backend=cast(Any, FakeBackend()))
    valid = _endpoint_names(cls)
    for name, value in returns.items():
        if name not in valid:
            raise TypeError(f"{cls.__name__} has no endpoint {name!r}; endpoints: {sorted(valid)}")
        mock = value if isinstance(value, Mock) else Mock(name=f"{cls.__name__}.{name}", return_value=value)
        setattr(instance, name, mock)
    return instance


_UNSET: Any = object()


@contextmanager
def mock_endpoint(
    client: BaseAPIClient[Any],
    name: str,
    *,
    return_value: Any = _UNSET,
    side_effect: Any = _UNSET,
    mock: Mock | None = None,
) -> Iterator[Mock]:
    """Override a single endpoint with a mock for the duration of a ``with`` block.

    The client-side counterpart to ``backend.mock_get(...)``: scoped and
    restoring, so it composes into yield-fixtures and nests cleanly. Works on any
    client — a real one, or a :func:`mock_client` — and restores whatever was
    there before (the real endpoint, or an outer mock)::

        @pytest.fixture
        def get_user(client):
            with mock_endpoint(client, "get_user", return_value=User(id="1", name="Ada")) as m:
                yield m

    Pass ``return_value`` (a domain object, not an HTTP response) and/or
    ``side_effect``, or supply your own ``mock``.
    """
    if name not in _endpoint_names(type(client)):
        raise TypeError(f"{type(client).__name__} has no endpoint {name!r}")

    m = mock if mock is not None else Mock(name=f"{type(client).__name__}.{name}")
    if return_value is not _UNSET:
        m.return_value = return_value
    if side_effect is not _UNSET:
        m.side_effect = side_effect

    had_previous = name in client.__dict__
    previous = client.__dict__.get(name)
    setattr(client, name, m)
    try:
        yield m
    finally:
        if had_previous:
            setattr(client, name, previous)
        else:
            client.__dict__.pop(name, None)  # remove instance attr -> descriptor visible again


def mock_of(client: BaseAPIClient[Any], name: str) -> Mock:
    """Return the ``Mock`` backing a mocked endpoint, for typed assertions.

    ``client.get_user`` is statically typed as the endpoint's return type, so
    ``client.get_user.assert_called_once()`` fails type checking. ``mock_of`` gives
    you the underlying mock without a cast::

        mock_of(client, "get_user").assert_called_once_with(GetUserRequest(user_id="1"))
    """
    attr = getattr(client, name)
    if not isinstance(attr, Mock):
        raise TypeError(f"endpoint {name!r} is not mocked on this client")
    return attr
