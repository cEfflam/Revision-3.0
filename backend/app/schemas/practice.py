"""Schémas de l'entraînement type examen."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Subject
from app.schemas.ai import SourceRead


class ExamFormatRead(BaseModel):
    """Décrit à l'interface — et à l'étudiant — ce qui est attendu."""

    model_config = ConfigDict(from_attributes=True)

    subject: str = ""
    label: str
    input_kind: str
    method: str
    criteria: list[str]
    duration_minutes: int
    total_points: int
    placeholder: str


class ExamQuestion(BaseModel):
    number: int
    text: str
    points: float = 0


class ExamGenerateRequest(BaseModel):
    subject: Subject
    # Thème imposé : sans lui, le sujet porte sur les notions les plus fragiles.
    topic: str = Field(default="", max_length=300)
    node_id: int | None = None


class ExamRead(BaseModel):
    subject: str
    format: ExamFormatRead
    title: str
    instructions: str = ""
    context: str = ""
    questions: list[ExamQuestion] = Field(default_factory=list)
    duration_minutes: int = 45
    total_points: float = 20
    inspired_by: str = ""
    # Notions que ce sujet met à l'épreuve. Renvoyées au client puis reprises
    # à la correction : c'est ce qui permet à une mauvaise note de faire
    # baisser la maîtrise des bonnes notions, et de les remettre en révision.
    target_node_ids: list[int] = Field(default_factory=list)
    # False quand aucune annale n'a été trouvée : le sujet est alors construit
    # sur la méthode officielle seule, et l'interface le signale.
    has_annales: bool = False
    sources: list[SourceRead] = Field(default_factory=list)
    model: str = ""
    mocked: bool = False


class ExamEvaluateRequest(BaseModel):
    subject: Subject
    # Le sujet est renvoyé tel quel par le client : l'exercice n'est pas
    # persisté, exactement comme le quiz. Ce qui doit durer, c'est la trace
    # de progression, pas le brouillon.
    exercise: dict
    answer: str = Field(min_length=1, max_length=20000)


class QuestionFeedback(BaseModel):
    number: int
    points_earned: float = 0
    points_max: float = 0
    feedback: str = ""


class CriterionFeedback(BaseModel):
    criterion: str
    verdict: str = "fragile"
    comment: str = ""


class MasteryImpact(BaseModel):
    """Effet de la copie sur une notion du graphe."""

    node_id: int
    node_title: str
    delta: float
    mastery_after: float


class ExamEvaluationRead(BaseModel):
    score: float = 0
    max_score: float = 20
    # Ce que cette copie a changé dans le graphe. Rendre l'effet visible évite
    # l'impression que la note « ne sert à rien ».
    mastery_impact: list[MasteryImpact] = Field(default_factory=list)
    cards_resurfaced: int = 0
    per_question: list[QuestionFeedback] = Field(default_factory=list)
    criteria_feedback: list[CriterionFeedback] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_step: str = ""
    model: str = ""
    mocked: bool = False
