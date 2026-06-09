#!/usr/bin/env python3
"""
Example: PokeAPI Client using clientcraft.

This example demonstrates how to use the clientcraft library to build
a declarative client for the PokeAPI (https://pokeapi.co/).

Run with:
    uv run python example.py
"""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel

from clientcraft import AsyncGet
from clientcraft.async_client import AsyncAPIClient
from clientcraft.backends.aiohttp import AiohttpBackend

# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class GetPokemonRequest(BaseModel):
    """Request to get a Pokemon by name or ID."""

    name: str  # This will be used as a path parameter


class GetPokemonListRequest(BaseModel):
    """Request to list Pokemon with pagination."""

    limit: int = 20
    offset: int = 0


class GetTypeRequest(BaseModel):
    """Request to get a Pokemon type by name."""

    name: str


# ---------------------------------------------------------------------------
# Response Models (simplified - PokeAPI returns much more data)
# ---------------------------------------------------------------------------


class NamedResource(BaseModel):
    """A named API resource reference."""

    name: str
    url: str


class PokemonType(BaseModel):
    """Pokemon type slot."""

    slot: int
    type: NamedResource


class PokemonAbility(BaseModel):
    """Pokemon ability slot."""

    ability: NamedResource
    is_hidden: bool
    slot: int


class PokemonStat(BaseModel):
    """Pokemon base stat."""

    base_stat: int
    effort: int
    stat: NamedResource


class Pokemon(BaseModel):
    """Pokemon details response."""

    id: int
    name: str
    height: int  # in decimeters
    weight: int  # in hectograms
    types: list[PokemonType]
    abilities: list[PokemonAbility]
    stats: list[PokemonStat]
    base_experience: int | None = None


class PokemonListResponse(BaseModel):
    """List of Pokemon with pagination."""

    count: int
    next: str | None
    previous: str | None
    results: list[NamedResource]


class TypePokemon(BaseModel):
    """A Pokemon that has a certain type."""

    slot: int
    pokemon: NamedResource


class PokemonTypeResponse(BaseModel):
    """Pokemon type details."""

    id: int
    name: str
    pokemon: list[TypePokemon]


# ---------------------------------------------------------------------------
# Async PokeAPI Client
# ---------------------------------------------------------------------------


class PokeAPIClient(AsyncAPIClient):
    """
    Async client for PokeAPI.

    Example:
        async with AiohttpBackend() as backend:
            client = PokeAPIClient(
                base_url="https://pokeapi.co/api/v2",
                backend=backend
            )
            pikachu = await client.get_pokemon(GetPokemonRequest(name="pikachu"))
            print(f"Pikachu weighs {pikachu.weight / 10} kg")
    """

    get_pokemon: AsyncGet[GetPokemonRequest, Pokemon, Literal["/pokemon/{name}"]]
    list_pokemon: AsyncGet[GetPokemonListRequest, PokemonListResponse, Literal["/pokemon"]]
    get_type: AsyncGet[GetTypeRequest, PokemonTypeResponse, Literal["/type/{name}"]]


# ---------------------------------------------------------------------------
# Demo Functions
# ---------------------------------------------------------------------------


async def demo_get_pokemon() -> None:
    """Demonstrate fetching a single Pokemon."""
    print("\n" + "=" * 60)
    print("Demo: Fetching a single Pokemon")
    print("=" * 60)

    async with AiohttpBackend() as backend:
        client = PokeAPIClient(
            base_url="https://pokeapi.co/api/v2",
            backend=backend,
        )

        # Get Pikachu!
        pikachu = await client.get_pokemon(GetPokemonRequest(name="pikachu"))
        assert isinstance(pikachu, Pokemon)

        print(f"\n🔵 {pikachu.name.upper()}")
        print(f"   ID: #{pikachu.id}")
        print(f"   Height: {pikachu.height / 10} m")
        print(f"   Weight: {pikachu.weight / 10} kg")
        print(f"   Types: {', '.join(t.type.name for t in pikachu.types)}")
        print(f"   Abilities: {', '.join(a.ability.name for a in pikachu.abilities)}")
        print("   Base Stats:")
        for stat in pikachu.stats:
            bar = "█" * (stat.base_stat // 10) + "░" * (10 - stat.base_stat // 10)
            print(f"      {stat.stat.name:20} {bar} {stat.base_stat}")


async def demo_list_pokemon() -> None:
    """Demonstrate listing Pokemon with pagination."""
    print("\n" + "=" * 60)
    print("Demo: Listing Pokemon (with pagination)")
    print("=" * 60)

    async with AiohttpBackend() as backend:
        client = PokeAPIClient(
            base_url="https://pokeapi.co/api/v2",
            backend=backend,
        )

        # Get first 10 Pokemon
        result = await client.list_pokemon(GetPokemonListRequest(limit=10, offset=0))
        assert isinstance(result, PokemonListResponse)

        print(f"\nTotal Pokemon in database: {result.count}")
        print("\nFirst 10 Pokemon:")
        for i, pokemon in enumerate(result.results, 1):
            print(f"   {i}. {pokemon.name}")


async def demo_get_type() -> None:
    """Demonstrate fetching type information."""
    print("\n" + "=" * 60)
    print("Demo: Fetching Pokemon by Type")
    print("=" * 60)

    async with AiohttpBackend() as backend:
        client = PokeAPIClient(
            base_url="https://pokeapi.co/api/v2",
            backend=backend,
        )

        # Get Fire type Pokemon
        fire_type = await client.get_type(GetTypeRequest(name="fire"))
        assert isinstance(fire_type, PokemonTypeResponse)

        print(f"\n🔥 Fire Type Pokemon (showing first 10 of {len(fire_type.pokemon)}):")
        for tp in fire_type.pokemon[:10]:
            print(f"   • {tp.pokemon.name}")


async def demo_compare_pokemon() -> None:
    """Demonstrate fetching multiple Pokemon concurrently."""
    print("\n" + "=" * 60)
    print("Demo: Comparing Pokemon (concurrent requests)")
    print("=" * 60)

    async with AiohttpBackend() as backend:
        client = PokeAPIClient(
            base_url="https://pokeapi.co/api/v2",
            backend=backend,
        )

        # Fetch three starter Pokemon concurrently
        results = await asyncio.gather(
            client.get_pokemon(GetPokemonRequest(name="bulbasaur")),
            client.get_pokemon(GetPokemonRequest(name="charmander")),
            client.get_pokemon(GetPokemonRequest(name="squirtle")),
        )

        print("\n🌿🔥💧 Kanto Starters Comparison:")
        print("-" * 50)
        print(f"{'Name':<12} {'Types':<20} {'HP':<6} {'Attack':<8} {'Defense'}")
        print("-" * 50)

        for pokemon in results:
            assert isinstance(pokemon, Pokemon)
            types = "/".join(t.type.name for t in pokemon.types)
            stats = {s.stat.name: s.base_stat for s in pokemon.stats}
            print(
                f"{pokemon.name.capitalize():<12} "
                f"{types:<20} "
                f"{stats.get('hp', 0):<6} "
                f"{stats.get('attack', 0):<8} "
                f"{stats.get('defense', 0)}"
            )


async def main() -> None:
    """Run all demos."""
    print("\n" + "🎮 " * 20)
    print("   clientcraft Example: PokeAPI Client")
    print("🎮 " * 20)

    await demo_get_pokemon()
    await demo_list_pokemon()
    await demo_get_type()
    await demo_compare_pokemon()

    print("\n" + "=" * 60)
    print("✅ All demos completed successfully!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
