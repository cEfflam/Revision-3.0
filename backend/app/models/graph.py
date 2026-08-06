"""
Graphe de connaissances : les nœuds (notions) et les arêtes (dépendances).

C'est la colonne vertébrale de REVISIO. Une note isolée ne dit rien ; un nœud
relié à ses prérequis permet de répondre à la vraie question :

    « Pourquoi est-ce que je ne comprends pas Doctrine ? »
    → parce que `relations SQL` (prérequis) est à 34 % de maîtrise.

Le graphe est un DAG : les arêtes `prerequisite` ne doivent jamais former de
cycle, sinon rien ne serait jamais débloquable. La vérification est faite
côté service (`services/graph/engine.py`), pas par la base.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
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
from app.models.enums import EdgeRelation, NodeKind, NodeStatus, Subject

if TYPE_CHECKING:
    from app.models.learning import Card
    from app.models.user import User


class KnowledgeNode(Base, TimestampMixin):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (
        # Le slug identifie la notion de façon lisible et stable, par
        # utilisateur : `sql-inner-join`, `symfony-doctrine-orm`…
        UniqueConstraint("user_id", "slug", name="uq_node_slug"),
        Index("ix_node_user_status", "user_id", "status"),
        Index("ix_node_user_parent", "user_id", "parent_id"),
        CheckConstraint("mastery >= 0 AND mastery <= 1", name="mastery_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    slug: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16), default=NodeKind.concept.value)
    subject: Mapped[str] = mapped_column(String(32), default=Subject.other.value)
    description: Mapped[str] = mapped_column(Text, default="")

    # ── Hiérarchie de CONTENANCE : Matière > Thème > Notion ──────────────
    # Volontairement distincte des arêtes de prérequis. Les deux répondent à
    # des questions différentes et se croisent :
    #   parent_id  → « où cette notion se range-t-elle dans mon référentiel ? »
    #   NodeEdge   → « que faut-il maîtriser avant de l'aborder ? »
    # Doctrine ORM est rangé sous « Symfony » mais a pour prérequis une notion
    # de SQL, dans une tout autre branche. Confondre les deux relations rendrait
    # l'un des deux usages impossible.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=True
    )
    # Rang d'affichage dans la fratrie : le référentiel a un ordre pédagogique
    # qui n'est ni alphabétique ni chronologique.
    position: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )

    # ── État d'acquisition ───────────────────────────────────────────────
    # mastery ∈ [0,1] : moyenne pondérée des performances récentes.
    mastery: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        String(16), default=NodeStatus.available.value
    )
    # Difficulté intrinsèque (1 = trivial, 5 = ardu) : influence l'estimation
    # du temps d'apprentissage dans la roadmap.
    difficulty: Mapped[int] = mapped_column(
        Integer, default=3, server_default=text("3")
    )
    estimated_minutes: Mapped[int] = mapped_column(
        Integer, default=20, server_default=text("20")
    )

    # ── Synthèse consolidée ──────────────────────────────────────────────
    # Texte unique fusionnant tout ce que l'utilisateur a importé sur cette
    # notion : cours, fiche de révision, annotations, exercices. Sert de
    # contexte PRINCIPAL à l'IA, les fragments bruts venant en appui pour le
    # détail exact. Six fragments épars qui se recoupent coûtent plus cher et
    # donnent une vision plus confuse qu'un texte dense et ordonné.
    synthesis: Mapped[str] = mapped_column(Text, default="")
    synthesis_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Nombre de documents ayant servi à la construire : si de nouveaux
    # documents sont rattachés depuis, la synthèse est périmée.
    synthesis_source_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )

    last_studied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    failure_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )

    user: Mapped[User] = relationship(back_populates="nodes")
    cards: Mapped[list[Card]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )
    children: Mapped[list[KnowledgeNode]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="KnowledgeNode.position",
        # `remote_side` désigne le côté « un » de la relation réflexive :
        # sans lui, SQLAlchemy ne sait pas dans quel sens lire parent_id.
        single_parent=True,
    )
    parent: Mapped[KnowledgeNode | None] = relationship(
        back_populates="children", remote_side=[id]
    )

    # Arêtes sortantes : « ce nœud débloque… »
    outgoing_edges: Mapped[list[NodeEdge]] = relationship(
        foreign_keys="NodeEdge.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    # Arêtes entrantes : « ce nœud dépend de… »
    incoming_edges: Mapped[list[NodeEdge]] = relationship(
        foreign_keys="NodeEdge.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Node {self.slug} mastery={self.mastery:.2f}>"


class NodeEdge(Base, TimestampMixin):
    """
    Arête orientée. Lecture : `source` → `target`.
    Avec relation=`prerequisite`, il faut maîtriser source pour ouvrir target.
    """

    __tablename__ = "node_edges"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation", name="uq_edge"),
        CheckConstraint("source_id <> target_id", name="no_self_loop"),
        Index("ix_edge_target", "target_id", "relation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True
    )
    relation: Mapped[str] = mapped_column(
        String(16), default=EdgeRelation.prerequisite.value
    )
    # Force de la dépendance (0→1) : un prérequis à 1.0 bloque totalement,
    # à 0.3 il n'est qu'un signal de révision.
    weight: Mapped[float] = mapped_column(Float, default=1.0, server_default=text("1"))

    source: Mapped[KnowledgeNode] = relationship(
        foreign_keys=[source_id], back_populates="outgoing_edges"
    )
    target: Mapped[KnowledgeNode] = relationship(
        foreign_keys=[target_id], back_populates="incoming_edges"
    )

    def __repr__(self) -> str:
        return f"<Edge {self.source_id}--{self.relation}-->{self.target_id}>"
