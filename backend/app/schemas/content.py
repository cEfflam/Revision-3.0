"""Schémas des documents et de la recherche sémantique."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentCollection, Subject


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    original_filename: str
    mime_type: str
    size_bytes: int
    collection: str
    subject: str
    status: str
    error_message: str
    char_count: int
    chunk_count: int
    summary: str
    created_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    collection: DocumentCollection | None = None
    subject: Subject | None = None


class IngestResponse(BaseModel):
    document: DocumentRead
    chunk_count: int
    vectors_indexed: int
    warning: str = ""


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordinal: int
    heading: str
    content: str
    char_count: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    collections: list[DocumentCollection] = Field(default_factory=list)
    subject: Subject | None = None
    top_k: int = Field(default=6, ge=1, le=30)


class SearchHitRead(BaseModel):
    document_title: str
    heading: str
    excerpt: str
    score: float
    document_id: int | None = None
    ordinal: int | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitRead]
    embedder: str
