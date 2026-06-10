# API Reference

Auto-generated from docstrings. Work in progress

## Clients

::: clientcraft.client.APIClient

::: clientcraft.async_client.AsyncAPIClient

## Endpoint types

The endpoint types (`Get`, `Post`, `Put`, `Patch`, `Delete` and their `Async*`
counterparts) are constructed at runtime via a metaclass and described
statically by the bundled type stubs. See [How It Works](how-it-works.md) for the
mechanism and [Endpoints](endpoints.md) for usage.

## Response wrappers

::: clientcraft.TextResponse

::: clientcraft.BytesResponse

## Errors

::: clientcraft.HttpError

## Core types

::: clientcraft.RequestStyle

::: clientcraft.ResponseStyle

::: clientcraft.EndpointInfo

::: clientcraft.ExtractedEndpoint

## Backend protocols

::: clientcraft.backends.HttpBackend

::: clientcraft.backends.AsyncHttpBackend

::: clientcraft.backends.HttpResponse
