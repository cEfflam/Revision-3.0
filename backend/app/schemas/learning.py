"""Schémas des cartes SRS, des révisions et du tableau de bord."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CardKind, LearningEngine, Rating
from app.schemas.graph import NodeRead
from app.schemas.onboarding import GoalRead


# ═════════════════════════════════════════════════════════════════════════
#  Cartes
# ═════════════════════════════════════════════════════════════════════════
class CardCreate(BaseModel):
    front: str = Field(min_length=1, max_length=4000)
    back: str = Field(min_length=1, max_length=8000)
    kind: CardKind = CardKind.basic
    hint: str = Field(default="", max_length=2000)
    explanation: str = Field(default="", max_length=4000)
    node_id: int | None = None
    document_id: int | None = None


class CardUpdate(BaseModel):
    front: str | None = Field(default=None, max_length=4000)
    back: str | None = Field(default=None, max_length=8000)
    hint: str | None = Field(default=None, max_length=2000)
    explanation: str | None = Field(default=None, max_length=4000)
    node_id: int | None = None
    is_suspended: bool | None = None


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    front: str
    back: str
    kind: str
    hint: str
    explanation: str
    state: str
    due_at: datetime
    interval_days: float
    ease_factor: float
    repetitions: int
    lapses: int
    node_id: int | None = None
    document_id: int | None = None
    ai_generated: bool = False


class CardQueueItem(CardRead):
    """Carte enrichie du contexte affiché pendant la révision."""

    node_title: str | None = None
    node_subject: str | None = None


# ═════════════════════════════════════════════════════════════════════════
#  Révision
# ═════════════════════════════════════════════════════════════════════════
class ReviewRequest(BaseModel):
    rating: Rating
    # Temps de réflexion mesuré par le frontend. Un « good » obtenu en 15 s ne
    # traduit pas la même solidité qu'un « good » instantané.
    duration_ms: int = Field(default=0, ge=0, le=3_600_000)


class ReviewResponse(BaseModel):
    card: CardRead
    next_due_at: datetime
    interval_days: float
    # Rempli seulement en cas d'échec : les prérequis qui expliquent l'erreur.
    weak_prerequisites: list[NodeRead] = Field(default_factory=list)
    diagnosis: str = ""
    remaining_due: int = 0


class GenerateCardsRequest(BaseModel):
    """Génération de cartes par l'IA, depuis un document ou un texte collé."""

    document_id: int | None = None
    text: str = Field(default="", max_length=20000)
    count: int = Field(default=8, ge=1, le=30)
    node_id: int | None = None


class GenerateCardsResponse(BaseModel):
    created: int
    cards: list[CardRead]
    model: str
    mocked: bool


# ═════════════════════════════════════════════════════════════════════════
#  Sessions
# ═════════════════════════════════════════════════════════════════════════
class SessionStart(BaseModel):
    engine: LearningEngine = LearningEngine.srs
    node_id: int | None = None
    planned_minutes: int = Field(default=25, ge=5, le=180)


class SessionEnd(BaseModel):
    cards_reviewed: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    engine: str
    node_id: int | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    cards_reviewed: int
    correct_count: int
    summary: str


# ═════════════════════════════════════════════════════════════════════════
#  Dashboard « Aujourd'hui »
# ═════════════════════════════════════════════════════════════════════════
class HeatmapPoint(BaseModel):
    day: date
    minutes: int
    reviews: int
    xp: int


class TodayAction(BaseModel):
    """Une ligne de la liste d'actions prioritaires du dashboard."""

    key: str
    icon: str
    title: str
    subtitle: str
    href: str
    count: int | None = None
    accent: str = "indigo"


class DashboardRead(BaseModel):
    greeting: str
    goal: GoalRead | None = None
    days_left: int | None = None
    readiness: float = 0.0
    due_now: int = 0
    daily_minutes: int = 30
    streak_current: int = 0
    streak_best: int = 0
    minutes_today: int = 0
    actions: list[TodayAction] = Field(default_factory=list)
    weakest_nodes: list[NodeRead] = Field(default_factory=list)
    heatmap: list[HeatmapPoint] = Field(default_factory=list)


class StatsRead(BaseModel):
    total_cards: int
    new_cards: int
    mastered_cards: int
    reviews_total: int
    accuracy: float
    due_now: int
    nodes_total: int
    nodes_mastered: int
    documents_total: int
    subject_mastery: dict[str, float] = Field(default_factory=dict)
