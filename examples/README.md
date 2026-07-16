# Examples

Runnable examples for `clientcraft`. Each file is self-contained.

## Usage

| File | What it shows | Run |
| --- | --- | --- |
| [`basic_usage.py`](basic_usage.py) | A declarative async client against the live PokeAPI | `uv run python examples/basic_usage.py` |
| [`error_handling.py`](error_handling.py) | Translating HTTP errors into domain exceptions (`Raises`, `DomainError`, `DEFAULT`, `handle_error`) | `uv run python examples/error_handling.py` |

## Testing

The library exposes two interfaces, and you test them from opposite sides:

- **backend → client** — fake the transport, run the real client. Test that
  *your client* serializes, parses, and maps errors correctly.
- **client → your code** — stub the client, run your application. Test that
  *your code* uses the client correctly.

| File | Direction | Run |
| --- | --- | --- |
| [`testing_your_client.py`](testing_your_client.py) | backend → client (`FakeBackend`) | `uv run pytest examples/testing_your_client.py -v` |
| [`testing_your_app.py`](testing_your_app.py) | client → your code (`mock_client` / `mock_endpoint`) | `uv run pytest examples/testing_your_app.py -v` |

See the [Testing guide](../docs/testing.md) for the full reference.
