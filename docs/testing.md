# Testing

A `clientcraft` client sits between two interfaces: the **HTTP responses coming in
from the backend**, and the **domain objects it hands out to your code**. You test
those two sides from opposite directions, and `clientcraft.testing` gives you a
tool for each:

| You're testing… | Direction | Tool |
| --- | --- | --- |
| **your client** — does it serialize, parse, and map errors correctly? | fake the **backend**, run the real client | [`FakeBackend`](#testing-your-client-fakebackend) |
| **your application** — does your code use the client correctly? | stub the **client**, run your code | [`mock_client`](#testing-your-application-mock_client) |

Pick by what's *under test*. If the client is the thing you're verifying, fake the
backend so all its real behaviour runs. If the client is just a dependency of the
code you're verifying, stub it — don't route through HTTP you don't care about.

Everything lives in `clientcraft.testing`, a dedicated namespace (not with the
production backends) — these are test doubles, not something you'd ship.

Runnable examples: [`examples/testing_your_client.py`](https://github.com/SunBright-Technologies/clientcraft/blob/main/examples/testing_your_client.py)
and [`examples/testing_your_app.py`](https://github.com/SunBright-Technologies/clientcraft/blob/main/examples/testing_your_app.py).

## Testing your client (`FakeBackend`)

`FakeBackend` fakes the transport and lets the real client run — so serialization,
parsing, and your [error handling](error-handling.md) are all exercised. Its
routes are backed by `unittest.mock.Mock`s, so you keep the full mock toolbox
(`return_value`, `side_effect`, `wraps`) and per-route call assertions.

```python
from clientcraft.testing import FakeBackend      # or FakeAsyncBackend
```

### Registering a response

`mock_get`, `mock_post`, `mock_put`, `mock_patch`, `mock_delete` (and the generic
`mock`) are **context managers that yield a `Mock`**. The `url` is matched as a
substring of the full request URL. Pass a dict, list, or Pydantic model as
`json=`:

```python
def test_get_user():
    backend = FakeBackend()
    with backend.mock_get("/users/123", json={"id": "123", "name": "Ada"}) as m:
        client = UserAPI(base_url="https://api.example.com", backend=backend)

        user = client.get_user(GetUserRequest(user_id="123"))

        assert user.name == "Ada"
        m.assert_called_once()
```

Other bodies: `text="..."`, `content=b"..."`, or `response=FakeResponse(...)` for
full control. Set `status=` to drive error handling, and `headers=` for response
headers.

### Inspecting the call

The yielded mock records every call; the request is passed as a `RecordedRequest`
(`.method`, `.url`, `.headers`, `.content`, and a `.json()` helper for the body):

```python
with backend.mock_post("/users", json={"id": "9", "name": "Lin"}) as m:
    client.create_user(CreateUserRequest(name="Lin"))

m.assert_called_once()
sent = m.call_args.args[0]
assert sent.method == "POST"
assert sent.json() == {"name": "Lin"}
```

### Dynamic responses & failures

Because it's a real `Mock`, use `side_effect` for sequences or to simulate a
transport failure:

```python
with backend.mock_get("/users/1") as m:
    m.side_effect = [
        FakeResponse(200, b'{"id":"1","name":"first"}', {}),
        FakeResponse(200, b'{"id":"1","name":"second"}', {}),
    ]
    # first call -> "first", second call -> "second"

with backend.mock_get("/users/1") as m:
    m.side_effect = ConnectionError("boom")   # raised like a real network error
```

### Fixtures and overriding

Registrations are a **stack**: the most recently entered one wins, and leaving
its block pops it, restoring whatever was registered before. That makes fixtures
compose — a fixture registers a default, a test overrides it for a block:

```python
@pytest.fixture
def fake():
    return FakeBackend()

@pytest.fixture
def get_user(fake):
    with fake.mock_get("/users/1", json={"id": "1", "name": "default"}) as m:
        yield m

def test_override(fake, get_user):
    client = UserAPI(base_url="https://api.example.com", backend=fake)

    assert client.get_user(GetUserRequest(user_id="1")).name == "default"

    with fake.mock_get("/users/1", json={"id": "1", "name": "override"}):
        assert client.get_user(GetUserRequest(user_id="1")).name == "override"

    # back to the fixture's default once the block exits
    assert client.get_user(GetUserRequest(user_id="1")).name == "default"
```

A request matching no active route raises `AssertionError` listing the routes, so
unexpected calls fail loudly.

### Async

`FakeAsyncBackend` is identical — registration is the same, only the client is
awaited:

```python
backend = FakeAsyncBackend()
with backend.mock_get("/users/5", json={"id": "5", "name": "Async"}) as m:
    client = AsyncUserAPI(base_url="https://api.example.com", backend=backend)
    user = await client.get_user(GetUserRequest(user_id="5"))
    m.assert_called_once()
```

## Testing your application (`mock_client`)

The fake backend is the right tool for testing *your client* — it runs real
serialization, parsing, and error handling. But when you're testing code that
*depends on* a client (a service you'd inject one into), you often just want to
stub the endpoint and assert it was called, at the Python level.

**Scoped-patch a real client** — this is plain `unittest.mock`, no clientcraft
helper needed (endpoints are patchable attributes):

```python
from unittest.mock import patch

with patch.object(client, "get_user", return_value=User(id="1", name="Ada")) as m:
    service.do_thing()
    m.assert_called_once_with(GetUserRequest(user_id="1"))
# original endpoint restored on exit
```

**Build an injectable fake client** — when you don't want a real client (or a
backend) at all, `mock_client` gives you one whose endpoints are mocks:

```python
from clientcraft.testing import mock_client, mock_of

client = mock_client(UserAPI, get_user=User(id="1", name="Ada"))
service = MyService(client)            # inject it — it *is* a UserAPI
service.run()

mock_of(client, "get_user").assert_called_once_with(GetUserRequest(user_id="1"))
```

Each keyword sets that endpoint's `return_value`; pass a `Mock` for full control
(e.g. `get_user=Mock(side_effect=[...])`). Only the endpoints you name are mocked
— calling an unmocked one raises loudly, so a forgotten stub can't pass silently.
`mock_of(client, name)` returns the underlying `Mock` for assertions (accessing
`client.get_user` directly is statically typed as the *response*, so `.assert_*`
wouldn't type-check).

**Scope one endpoint with `mock_endpoint`** — the client-side counterpart to the
backend's `mock_get`: a context manager that overrides an endpoint for the block
and restores whatever was there before (a real endpoint, or an outer stub). It
composes into yield-fixtures and nests, just like the backend routes:

```python
from clientcraft.testing import mock_endpoint

@pytest.fixture
def get_user(client):
    with mock_endpoint(client, "get_user", return_value=User(id="1", name="Ada")) as m:
        yield m

def test_uses_it(client, get_user):
    ...
    get_user.assert_called_once()
```

Pass `return_value` (a domain object, not an HTTP response) and/or `side_effect`,
or supply your own `mock=`. Works on a real client or a `mock_client`.

!!! note "Which to use"
    Testing the **client** (does it serialize/parse/map errors right?) → **fake
    backend**. Testing code that **uses** a client as a collaborator → patch it or
    `mock_client`. Don't mock the endpoint when the client *is* what's under test,
    or you test the mock instead of your code.
