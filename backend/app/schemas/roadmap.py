"""Schémas du parcours d'apprentissage généré par l'IA."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoadmapGenerateRequest(BaseModel):
    # Par défaut, l'objectif principal de l'utilisateur.
    goal_id: int | None = None
    # Remplace le parcours existant. False = refuse si un parcours existe déjà,
    # pour éviter d'écraser un travail en cours par un double-clic.
    replace: bool = True
    max_steps: int = Field(default=12, ge=3, le=30)


class RoadmapStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    subject: str
    estimated_minutes: int
    why: str
    prerequisites: str
    node_id: int | None = None
    is_done: bool
    completed_at: datetime | None = None


class RoadmapStepUpdate(BaseModel):
    is_done: bool


class RoadmapRead(BaseModel):
    objective: str = ""
    feasible: bool = True
    advice: str = ""
    total_estimated_hours: float = 0.0
    steps: list[RoadmapStepRead] = Field(default_factory=list)
    generated_at: datetime | None = None
    model: str = ""
    mocked: bool = False
