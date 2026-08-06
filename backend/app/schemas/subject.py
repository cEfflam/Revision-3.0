"""
Schémas de la vue par matière.

Cette vue répond à une question que le dashboard ne traite pas : « je veux
bosser les maths MAINTENANT ». Le dashboard dit quoi faire ; ici, c'est
l'utilisateur qui décide de son angle d'attaque.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.content import DocumentRead
from app.schemas.graph import NodeRead


class SubjectSummary(BaseModel):
    """Une tuile de la liste des matières."""

    subject: str
    label: str
    mastery: float = 0.0
    nodes_total: int = 0
    nodes_mastered: int = 0
    nodes_critical: int = 0
    cards_total: int = 0
    cards_due: int = 0
    documents_total: int = 0


class SubjectDetail(SubjectSummary):
    """Écran d'une matière : tout ce qu'on peut y travailler."""

    nodes: list[NodeRead] = Field(default_factory=list)
    # Les notions les plus fragiles, déjà triées : c'est par là qu'il faut
    # commencer, et l'interface n'a pas à recalculer ce classement.
    weak_nodes: list[NodeRead] = Field(default_factory=list)
    documents: list[DocumentRead] = Field(default_factory=list)
    # Conseil d'attaque calculé côté serveur, comme les actions du dashboard.
    advice: str = ""
