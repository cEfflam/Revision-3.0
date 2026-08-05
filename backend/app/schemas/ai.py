"""Schémas des échanges avec les moteurs IA."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Subject
from app.services.ai.router import AiTask


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    document_title: str
    heading: str
    excerpt: str
    score: float


class HistoryMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    # Le moteur choisi détermine le prompt système, donc le comportement :
    # `math_hint` ne donnera jamais la réponse, `explain_code` structurera son
    # analyse en quatre points, etc.
    task: AiTask = AiTask.chat
    subject: Subject | None = None
    node_id: int | None = None
    # None = laisser le backend décider selon le moteur. Chercher dans les
    # documents n'a aucun intérêt pour une conversation en anglais, et coûte
    # une vectorisation à chaque message.
    use_rag: bool | None = None
    history: list[HistoryMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceRead] = Field(default_factory=list)
    model: str
    tier: str = ""
    mocked: bool = False
    latency_ms: int = 0
    tokens: int = 0


class WritingAnalysisRequest(BaseModel):
    """Audit d'un écrit de CGE (synthèse, écriture personnelle)."""

    text: str = Field(min_length=50, max_length=20000)


class WritingIssue(BaseModel):
    type: str
    severity: str = "info"
    label: str
    quote: str = ""
    detail: str = ""
    suggestion: str = ""


class WritingAnalysisResponse(BaseModel):
    score: float | None = None
    issues: list[WritingIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    next_step: str = ""
    model: str = ""
    mocked: bool = False


class AiStatusRead(BaseModel):
    """Diagnostic affiché dans les réglages : que fait l'IA en ce moment ?"""

    mocked: bool
    reason: str
    models: dict[str, str]
    embedder: str
    embedding_dim: int
    qdrant_reachable: bool
