"""Utilisateur, objectifs, auto-évaluation initiale (onboarding)."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import GoalKind

if TYPE_CHECKING:
    from app.models.content import Document
    from app.models.graph import KnowledgeNode
    from app.models.learning import Card, DailyActivity, StudySession


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), default="")

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    # ── Préférences d'apprentissage ──────────────────────────────────────
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Paris")
    # Budget quotidien déclaré à l'onboarding : le planificateur s'en sert
    # pour dimensionner la séance du jour.
    daily_minutes: Mapped[int] = mapped_column(
        Integer, default=30, server_default=text("30")
    )
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    # ── Motivation ───────────────────────────────────────────────────────
    streak_current: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    streak_best: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    last_active_day: Mapped[date | None] = mapped_column(Date, nullable=True)

    goals: Mapped[list[Goal]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    assessments: Mapped[list[SelfAssessment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    nodes: Mapped[list[KnowledgeNode]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cards: Mapped[list[Card]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[StudySession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    activities: Mapped[list[DailyActivity]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    roadmap_steps: Mapped[list[RoadmapStep]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email}>"


class Goal(Base, TimestampMixin):
    """
    Un objectif = une destination. « Avoir 16 au BTS SIO », « Devenir DevOps ».
    C'est l'entrée du générateur de roadmap.
    """

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32), default=GoalKind.diploma.value)
    description: Mapped[str] = mapped_column(Text, default="")

    # Date de l'épreuve : pilote l'urgence dans le planning quotidien.
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_minutes: Mapped[int] = mapped_column(
        Integer, default=30, server_default=text("30")
    )

    # Un seul objectif principal à la fois : c'est lui qu'affiche le dashboard.
    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    # 0.0 → 1.0, recalculé à partir de la maîtrise moyenne des nœuds liés.
    progress: Mapped[float] = mapped_column(
        Float, default=0.0, server_default=text("0")
    )

    user: Mapped[User] = relationship(back_populates="goals")

    def __repr__(self) -> str:
        return f"<Goal {self.id} {self.title!r}>"


class RoadmapStep(Base, TimestampMixin):
    """
    Une étape du parcours généré par l'IA.

    Persisté (contrairement au quiz) parce qu'un parcours se suit sur des
    semaines : on doit pouvoir cocher une étape, y revenir, et voir sa
    progression. Régénérer à chaque affichage coûterait un appel de modèle
    par ouverture d'écran, pour un contenu qui ne change pas.
    """

    __tablename__ = "roadmap_steps"
    __table_args__ = (Index("ix_roadmap_user_order", "user_id", "order_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=True
    )
    # Rattachement optionnel à une notion existante du graphe : permet de
    # lancer une session directement depuis une étape.
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), nullable=True
    )

    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(32), default="other")
    estimated_minutes: Mapped[int] = mapped_column(
        Integer, default=60, server_default=text("60")
    )
    # Pourquoi cette étape ICI et pas ailleurs — c'est ce qui distingue un
    # parcours d'une simple liste de sujets.
    why: Mapped[str] = mapped_column(Text, default="")
    # Titres des étapes prérequises, séparés par « | ». Pas de table de
    # liaison : ces dépendances sont descriptives et régénérées à chaque
    # roadmap, une normalisation coûterait plus qu'elle ne rapporte.
    prerequisites: Mapped[str] = mapped_column(Text, default="")

    is_done: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="roadmap_steps")

    def __repr__(self) -> str:
        return f"<RoadmapStep {self.order_index} {self.title!r}>"


class SelfAssessment(Base, TimestampMixin):
    """
    Niveau déclaré par l'utilisateur à l'onboarding (curseurs 0-100).
    Sert d'amorçage : sans lui, le système partirait de zéro sur toutes les
    matières et proposerait des révisions inutiles.
    """

    __tablename__ = "self_assessments"
    __table_args__ = (UniqueConstraint("user_id", "subject", name="uq_assessment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(32))
    level: Mapped[int] = mapped_column(Integer, default=50)

    user: Mapped[User] = relationship(back_populates="assessments")
