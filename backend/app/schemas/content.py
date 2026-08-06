"""Schémas des documents et de la recherche sémantique."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentCollection, Subject  # noqa: TC001


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


# ═════════════════════════════════════════════════════════════════════════
#  Rattachement d'un document aux notions du graphe
# ═════════════════════════════════════════════════════════════════════════
class NodeProposal(BaseModel):
    """Une notion détectée dans le document, et ce qu'on en fait."""

    title: str
    #: "certain"   → rattachement automatique à un nœud existant
    #: "suggested" → ressemblance probable, à confirmer
    #: "new"       → aucune correspondance, création proposée
    verdict: str
    score: float = 0.0
    matched_node_id: int | None = None
    matched_node_title: str = ""
    matched_node_subject: str = ""
    #: Matière devinée pour une nouvelle notion.
    suggested_subject: str = Subject.other.value
    #: Pré-coché dans l'interface pour les cas sûrs.
    selected: bool = False


class DocumentMappingRead(BaseModel):
    document_id: int
    document_title: str
    headings_found: int
    proposals: list[NodeProposal] = Field(default_factory=list)
    already_linked: list[int] = Field(default_factory=list)
    message: str = ""


class MappingDecision(BaseModel):
    title: str
    #: Renseigné pour rattacher à un nœud existant ; None pour en créer un.
    node_id: int | None = None
    subject: Subject = Subject.other
    create: bool = False


class ApplyMappingRequest(BaseModel):
    decisions: list[MappingDecision] = Field(default_factory=list)


class ApplyMappingResponse(BaseModel):
    created: int
    linked: int
    document_id: int
    message: str
