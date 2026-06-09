"""
Response wrapper types for non-JSON responses.

These Pydantic models wrap text and binary responses,
allowing the declarative API to handle all response types uniformly.
"""

from __future__ import annotations

from pydantic import BaseModel


class TextResponse(BaseModel):
    """
    Wrapper for text responses.

    Usage:
        get_health: Get[EmptyRequest, TextResponse, Literal["/health"]]
    """

    content: str


class BytesResponse(BaseModel):
    """
    Wrapper for binary responses.

    Usage:
        download_file: Get[FileRequest, BytesResponse, Literal["/files/{id}"]]
    """

    content: bytes
