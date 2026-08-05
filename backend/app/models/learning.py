"""
Apprentissage : cartes SRS, historique de révision, sessions, activité.

Les champs SRS portés par `Card` sont ceux de l'algorithme SM-2 :
  • ease_factor   — « facilité » de la carte, part de 2.5 et s'ajuste
  • interval_days — délai avant la prochaine présentation
  • repetitions   — succès consécutifs
  • lapses        — nombre d'oublis (utile pour repérer les cartes toxiques)

`ReviewLog` conserve chaque réponse. C'est volontairement redondant avec l'état
de la carte : sans historique, impossible de rejouer un autre algorithme (FSRS)
sur tes données passées, ni de dire « tu fais cette erreur depuis 3 semaines ».
"""

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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CardKind, CardState, LearningEngine

if TYPE_CHECKING:
    from app.models.content import Document
    from app.models.graph import KnowledgeNode
    from app.models.user import User

# Valeur de départ SM-2. 2.5 signifie « à chaque succès, l'intervalle ×2.5 ».
DEFAULT_EASE_FACTOR = 2.5


class Card(Base, TimestampMixin):
    __tablename__ = "cards"
    __table_args__ = (
        # L'index qui compte : « quelles cartes sont dues maintenant ? » est
        # LA requête du dashboard, jouée à chaque ouverture de l'app.
        Index("ix_card_due", "user_id", "due_at"),
        Index("ix_card_node", "node_id", "state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Rattachement au graphe : c'est ce lien qui fait remonter une réussite de
    # carte en progression de maîtrise sur la notion.
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), nullable=True
    )
    # Traçabilité : de quel document cette carte a-t-elle été extraite ?
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    kind: Mapped[str] = mapped_column(String(16), default=CardKind.basic.value)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    # Indice révélable avant la réponse (Active Recall assisté).
    hint: Mapped[str] = mapped_column(Text, default="")
    # Explication affichée après la réponse (technique de Feynman).
    explanation: Mapped[str] = mapped_column(Text, default="")

    is_suspended: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    ai_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    # ── État SRS ─────────────────────────────────────────────────────────
    state: Mapped[str] = mapped_column(String(16), default=CardState.new.value)
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    interval_days: Mapped[float] = mapped_column(
        Float, default=0.0, server_default=text("0")
    )
    ease_factor: Mapped[float] = mapped_column(
        Float, default=DEFAULT_EASE_FACTOR, server_default=text("2.5")
    )
    repetitions: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    lapses: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="cards")
    node: Mapped[KnowledgeNode | None] = relationship(back_populates="cards")
    document: Mapped[Document | None] = relationship(back_populates="cards")
    reviews: Mapped[list[ReviewLog]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Card {self.id} {self.state} due={self.due_at:%Y-%m-%d}>"


class ReviewLog(Base):
    """Une ligne par réponse donnée. Jamais modifiée, jamais supprimée."""

    __tablename__ = "review_logs"
    __table_args__ = (Index("ix_review_user_time", "user_id", "reviewed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    rating: Mapped[str] = mapped_column(String(8))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Temps réellement écoulé depuis la dernière révision (≠ prévu).
    elapsed_days: Mapped[float] = mapped_column(Float, default=0.0)
    # Nouvel intervalle décidé par l'algorithme.
    scheduled_days: Mapped[float] = mapped_column(Float, default=0.0)

    state_before: Mapped[str] = mapped_column(String(16), default=CardState.new.value)
    ease_before: Mapped[float] = mapped_column(Float, default=DEFAULT_EASE_FACTOR)
    ease_after: Mapped[float] = mapped_column(Float, default=DEFAULT_EASE_FACTOR)
    # Temps de réflexion en millisecondes : un « good » en 20 s ne vaut pas un
    # « good » en 2 s. Signal précieux pour la difficulté adaptative.
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    card: Mapped[Card] = relationship(back_populates="reviews")


class StudySession(Base, TimestampMixin):
    """Une session de travail : Mode Focus, série de flashcards, exercice…"""

    __tablename__ = "study_sessions"
    __table_args__ = (Index("ix_session_user_start", "user_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), nullable=True
    )

    engine: Mapped[str] = mapped_column(String(16), default=LearningEngine.srs.value)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )

    cards_reviewed: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    # Bilan rédigé par l'IA en fin de session (Journal d'apprentissage).
    summary: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="sessions")


class DailyActivity(Base, TimestampMixin):
    """
    Un enregistrement par jour travaillé. Alimente la heatmap façon GitHub et
    le calcul du streak. Agrégé à l'écriture plutôt que recalculé à la lecture :
    la heatmap affiche 365 jours, on ne veut pas 365 requêtes.
    """

    __tablename__ = "daily_activities"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_activity_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)

    minutes: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    reviews: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    cards_created: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    sessions_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Résumé du soir généré par l'IA.
    journal: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="activities")
