"""
Schémas de l'onboarding.

L'application a besoin de trois informations avant de pouvoir planifier quoi
que ce soit : où tu vas (l'objectif), d'où tu pars (le niveau déclaré) et
combien de temps tu as (minutes par jour). Sans ces trois éléments, un
planificateur ne peut produire qu'une liste générique.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import GoalKind, Subject


class GoalInput(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: GoalKind = GoalKind.diploma
    description: str = Field(default="", max_length=2000)
    target_date: date | None = None


class AssessmentInput(BaseModel):
    subject: Subject
    # Curseur 0-100 de l'écran d'auto-évaluation.
    level: int = Field(ge=0, le=100)


class OnboardingRequest(BaseModel):
    goal: GoalInput
    assessments: list[AssessmentInput] = Field(default_factory=list)
    daily_minutes: int = Field(default=30, ge=5, le=600)


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: str
    description: str
    target_date: date | None
    daily_minutes: int
    is_primary: bool
    is_active: bool
    progress: float

    # `computed_field` et non `property` : sans ce décorateur, Pydantic ne
    # sérialise pas le champ et le frontend ne le verrait jamais.
    @computed_field
    @property
    def days_left(self) -> int | None:
        if not self.target_date:
            return None
        return (self.target_date - date.today()).days


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject: str
    level: int


class OnboardingResponse(BaseModel):
    goal: GoalRead
    assessments: list[AssessmentRead]
    nodes_created: int
    message: str
