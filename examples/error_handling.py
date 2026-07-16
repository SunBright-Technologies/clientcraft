#!/usr/bin/env python3
"""
Example: Custom error handling with clientcraft.

Shows how to translate raw HTTP errors into your own *domain* exceptions
declaratively — so callers catch meaningful errors (``PokemonNotFound``) instead
of inspecting status codes at every call site.

Four ideas, all opt-in (a client that declares none behaves exactly as before,
raising ``HttpError`` on any status >= 400):

  1. Per-endpoint mapping via ``Raises(status, ExcType)`` in the annotation.
  2. Client-wide mapping via the ``errors`` class attribute.
  3. A ``DEFAULT`` catch-all key for any status without an exact mapping.
  4. Body-aware construction by overriding ``DomainError.from_http_error``.

Runs against the live PokeAPI (https://pokeapi.co/): a real 404 for an unknown
Pokemon, and a real 403 (Cloudflare) when the urllib user-agent is not set, which
the ``DEFAULT`` catch-all turns into ``PokeAPIError``. Dependency-free backend.

Run with:
    uv run python example_error_handling.py
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel

from clientcraft import DEFAULT, DomainError, ErrorMap, Get, HttpError, Raises
from clientcraft.backends.urllib import UrllibBackend
from clientcraft.client import APIClient

# ---------------------------------------------------------------------------
# Domain errors — your application's vocabulary, not HTTP's.
# ---------------------------------------------------------------------------


class PokemonNotFound(DomainError):
    """Raised when a Pokemon does not exist (HTTP 404).

    Default construction is fine — the original ``HttpError`` is attached on
    ``.http_error`` automatically.
    """


class PokeAPIError(DomainError):
    """Catch-all for any other PokeAPI error (not a 404).

    Overrides ``from_http_error`` to build a friendlier message from the response
    body — the imperative "read the body" logic lives on the exception, where it
    is reusable across every client that maps to it.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    @classmethod
    def from_http_error(cls, error: HttpError) -> DomainError:
        snippet = error.content.decode("utf-8", errors="replace")[:120]
        exc = cls(f"PokeAPI is unhappy (HTTP {error.status_code}): {snippet}")
        exc.http_error = error
        return exc


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class GetPokemonRequest(BaseModel):
    name: str  # path parameter


class Pokemon(BaseModel):
    id: int
    name: str
    weight: int


# ---------------------------------------------------------------------------
# Client — declarative error mapping alongside the endpoint declarations.
# ---------------------------------------------------------------------------


class PokeAPIClient(APIClient):
    """Tiny PokeAPI client with domain-error translation.

    - ``get_pokemon`` maps 404 -> ``PokemonNotFound`` (per-endpoint exact ``Raises``).
    - The client-wide ``errors`` map uses the ``DEFAULT`` catch-all: any error
      status without an exact mapping becomes ``PokeAPIError``.
    - Exact status always wins over ``DEFAULT``, so a 404 is still a
      ``PokemonNotFound``.
    """

    get_pokemon: Annotated[
        Get[GetPokemonRequest, Pokemon, Literal["/pokemon/{name}"]],
        Raises(404, PokemonNotFound),
    ]

    # DEFAULT catches everything else (403, 5xx, ...) across all endpoints.
    errors = ErrorMap({DEFAULT: PokeAPIError})


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("clientcraft — custom error handling demo")
    print("=" * 60)

    with UrllibBackend() as backend:
        client = PokeAPIClient(
            base_url="https://pokeapi.co/api/v2",
            backend=backend,
            # PokeAPI sits behind Cloudflare, which bans urllib's default UA.
            default_headers={"User-Agent": "clientcraft-example/1.0"},
        )

        # 1. Happy path — a real Pokemon.
        pikachu = client.get_pokemon(GetPokemonRequest(name="pikachu"))
        assert isinstance(pikachu, Pokemon)
        print(f"\n✅ Found: {pikachu.name} (#{pikachu.id}), weight={pikachu.weight}")

        # 2. Domain error — caller catches PokemonNotFound, never touches status codes.
        try:
            client.get_pokemon(GetPokemonRequest(name="definitely-not-a-pokemon"))
        except PokemonNotFound as err:
            print("\n✅ Caught domain error PokemonNotFound (from a real 404):")
            assert err.http_error is not None
            assert err.http_error.endpoint_info is not None
            print(f"   underlying status : {err.http_error.status_code}")
            print(f"   failed endpoint   : {err.http_error.endpoint_info.path}")
            # Note: PokemonNotFound is a DomainError, NOT an HttpError — the raw
            # HTTP error was translated away before it reached the caller.
            assert not isinstance(err, HttpError)

    # 3. Catch-all — a non-404 error (403 from Cloudflare, since this client omits
    #    the user-agent) resolves via the DEFAULT key, not the exact 404 mapping.
    with UrllibBackend() as banned_backend:
        banned = PokeAPIClient(base_url="https://pokeapi.co/api/v2", backend=banned_backend)
        try:
            banned.get_pokemon(GetPokemonRequest(name="pikachu"))
        except PokemonNotFound:
            print("\n(skipped catch-all demo: server did not return a non-404 error)")
        except PokeAPIError as err:
            assert err.http_error is not None
            print(f"\n✅ Caught catch-all PokeAPIError via DEFAULT (status {err.http_error.status_code}):")
            print(f"   {err.message}")

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
