"""
Point d'entrée unique des modèles.

IMPORTANT : chaque nouveau modèle doit être importé ici. SQLAlchemy résout les
relations par leur nom sous forme de chaîne (`"Card"`, `"NodeEdge"`…) ; si la
classe n'a jamais été importée, la résolution échoue au premier accès avec un
`InvalidRequestError` peu explicite. C'est aussi ce fichier qu'Alembic charge
pour comparer le schéma déclaré au schéma réel de la base.
"""

from app.models.base import Base, TimestampMixin
from app.models.content import Document, DocumentChunk
from app.models.enums import (
    CardKind,
    CardState,
    DocumentCollection,
    DocumentStatus,
    EdgeRelation,
    GoalKind,
    LearningEngine,
    NodeKind,
    NodeStatus,
    Rating,
    Subject,
)
from app.models.graph import KnowledgeNode, NodeEdge
from app.models.learning import (
    DEFAULT_EASE_FACTOR,
    Card,
    DailyActivity,
    ReviewLog,
    StudySession,
)
from app.models.user import Goal, SelfAssessment, User

__all__ = [
    "DEFAULT_EASE_FACTOR",
    "Base",
    "Card",
    "CardKind",
    "CardState",
    "DailyActivity",
    "Document",
    "DocumentChunk",
    "DocumentCollection",
    "DocumentStatus",
    "EdgeRelation",
    "Goal",
    "GoalKind",
    "KnowledgeNode",
    "LearningEngine",
    "NodeEdge",
    "NodeKind",
    "NodeStatus",
    "Rating",
    "ReviewLog",
    "SelfAssessment",
    "StudySession",
    "Subject",
    "TimestampMixin",
    "User",
]
