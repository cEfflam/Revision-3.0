"""
Documents importés et leurs fragments (chunks).

Répartition des rôles entre les deux bases :
  • PostgreSQL garde le TEXTE des chunks et les métadonnées → source de vérité,
    lisible, sauvegardable, requêtable en SQL.
  • Qdrant garde les VECTEURS → recherche par similarité sémantique.

`DocumentChunk.point_id` est le pont entre les deux : c'est l'UUID du point
Qdrant correspondant. Si Qdrant est perdu, on peut tout ré-indexer depuis
PostgreSQL sans avoir à relire les PDF d'origine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import DocumentCollection, DocumentStatus, Subject

# Un document couvre plusieurs notions, une notion apparaît dans plusieurs
# documents : une fiche de révision BTS SIO touche les onze matières à elle
# seule. Une simple colonne `node_id` sur Document serait donc fausse.
document_nodes = Table(
    "document_nodes",
    Base.metadata,
    Column(
        "document_id",
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "node_id",
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

if TYPE_CHECKING:
    from app.models.graph import KnowledgeNode
    from app.models.learning import Card
    from app.models.user import User


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        # Empêche d'importer deux fois le même fichier : on compare l'empreinte
        # SHA-256 du contenu, pas le nom de fichier.
        UniqueConstraint("user_id", "content_hash", name="uq_document_hash"),
        Index("ix_document_user_collection", "user_id", "collection"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(300))
    original_filename: Mapped[str] = mapped_column(String(300), default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    # Chemin relatif dans backend/storage — le fichier original est conservé
    # pour pouvoir ré-extraire avec un meilleur parser plus tard.
    storage_path: Mapped[str] = mapped_column(String(500), default="")

    collection: Mapped[str] = mapped_column(
        String(16), default=DocumentCollection.course.value
    )
    subject: Mapped[str] = mapped_column(String(32), default=Subject.other.value)

    status: Mapped[str] = mapped_column(
        String(16), default=DocumentStatus.pending.value, index=True
    )
    error_message: Mapped[str] = mapped_column(Text, default="")

    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    # Résumé exécutif produit à l'import (3 points clés).
    summary: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.ordinal",
    )
    cards: Mapped[list[Card]] = relationship(back_populates="document")
    # Notions couvertes par ce document, rapprochées du graphe à l'import.
    nodes: Mapped[list[KnowledgeNode]] = relationship(
        secondary=document_nodes, lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Document {self.id} {self.title!r} {self.status}>"


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunk_ordinal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    # Titre de la section d'origine : réinjecté dans le prompt pour que l'IA
    # sache d'où vient l'extrait qu'elle cite.
    heading: Mapped[str] = mapped_column(String(300), default="")
    # UUID du point correspondant dans Qdrant.
    point_id: Mapped[str] = mapped_column(String(36), index=True, default="")

    document: Mapped[Document] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk doc={self.document_id} #{self.ordinal}>"
