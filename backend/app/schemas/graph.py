"""Schémas du graphe de connaissances et du référentiel."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EdgeRelation, NodeKind, NodeStatus, Subject


class NodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=160)
    kind: NodeKind = NodeKind.concept
    subject: Subject = Subject.other
    description: str = Field(default="", max_length=4000)
    difficulty: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int = Field(default=20, ge=5, le=600)
    # Rattachement hiérarchique : le thème sous lequel ranger cette notion.
    parent_id: int | None = None
    position: int = Field(default=0, ge=0)
    # Slugs des prérequis : les arêtes sont créées dans la même transaction.
    prerequisites: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def normalise_slug(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None


class NodeUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    kind: NodeKind | None = None
    subject: Subject | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, ge=5, le=600)
    # Permet de corriger un niveau à la main (ex. après l'onboarding).
    mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    parent_id: int | None = None
    position: int | None = Field(default=None, ge=0)


class NodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    kind: str
    subject: str
    description: str
    mastery: float
    status: str
    difficulty: int
    estimated_minutes: int
    review_count: int
    failure_count: int
    last_studied_at: datetime | None = None
    parent_id: int | None = None
    position: int = 0


class CurriculumNode(NodeRead):
    """Nœud du référentiel, avec ses enfants — pour l'affichage en arbre."""

    children: list[CurriculumNode] = Field(default_factory=list)
    documents_count: int = 0
    cards_count: int = 0


class CurriculumRead(BaseModel):
    subject: str
    label: str
    themes: list[CurriculumNode] = Field(default_factory=list)
    #: Notions non rangées sous un thème — à classer.
    orphans: list[CurriculumNode] = Field(default_factory=list)


class EdgeCreate(BaseModel):
    source_id: int
    target_id: int
    relation: EdgeRelation = EdgeRelation.prerequisite
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class EdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    target_id: int
    relation: str
    weight: float


class GraphRead(BaseModel):
    """Payload complet pour la visualisation du Skill Tree."""

    nodes: list[NodeRead]
    edges: list[EdgeRead]
    counts: dict[str, int] = Field(default_factory=dict)


class DiagnosisRead(BaseModel):
    """Réponse à « pourquoi je bloque sur cette notion ? »."""

    node: NodeRead
    weak_prerequisites: list[NodeRead]
    verdict: str


class NodeStatusCount(BaseModel):
    status: NodeStatus
    count: int
