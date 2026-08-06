"""
Entraînement type examen.

Réponse à une question simple : « j'ai des BTS blancs de l'an dernier, est-ce
que l'appli peut s'en servir ? » — oui, et de la seule façon qui a du sens.

Les annales servent de MODÈLE DE FORME, jamais de banque de questions :
recopier un sujet déjà vu entraîne la mémoire du sujet, pas la compétence.
L'IA en tire la façon de poser les questions, le barème, le type de contexte,
puis invente un sujet neuf sur le contenu des cours.

Le sujet n'est pas persisté (comme le quiz). Ce qui doit durer, c'est la trace
de progression — la session et l'activité du jour, créditées à la correction.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.enums import SUBJECT_LABELS, LearningEngine, Subject
from app.models.graph import KnowledgeNode
from app.models.learning import StudySession
from app.schemas.ai import SourceRead
from app.schemas.practice import (
    CriterionFeedback,
    ExamEvaluateRequest,
    ExamEvaluationRead,
    ExamFormatRead,
    ExamGenerateRequest,
    ExamQuestion,
    ExamRead,
    MasteryImpact,
    QuestionFeedback,
)
from app.services.ai import service as ai_service
from app.services.ai.exam_formats import EXAM_FORMATS, format_for
from app.services.graph import engine as graph_engine
from app.services.srs import service as srs_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/practice", tags=["entraînement examen"])


def _format_read(subject: str) -> ExamFormatRead:
    fmt = format_for(subject)
    return ExamFormatRead(
        subject=subject,
        label=fmt.label,
        input_kind=fmt.input_kind,
        method=fmt.method,
        criteria=list(fmt.criteria),
        duration_minutes=fmt.duration_minutes,
        total_points=fmt.total_points,
        placeholder=fmt.placeholder,
    )


@router.get(
    "/formats",
    response_model=list[ExamFormatRead],
    summary="Format d'épreuve de chaque matière",
)
async def list_formats() -> list[ExamFormatRead]:
    """
    Ce qui est attendu matière par matière : type d'épreuve, méthode, critères
    de notation, durée et barème. Consommé par l'interface pour adapter le
    champ de réponse — et par l'étudiant pour savoir sur quoi il est jugé.
    """
    return [_format_read(subject) for subject in EXAM_FORMATS]


@router.post(
    "/generate",
    response_model=ExamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un sujet dans le style de mes annales",
)
async def generate_exam(
    payload: ExamGenerateRequest, user: CurrentUser, db: DbSession
) -> ExamRead:
    subject = payload.subject.value

    node_titles: list[str] = []
    target_ids: list[int] = []
    if payload.node_id:
        node = await db.get(KnowledgeNode, payload.node_id)
        if node is None or node.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Notion introuvable."
            )
        node_titles = [node.title]
        target_ids = [node.id]
    else:
        # Sans notion imposée, on vise les plus fragiles de la matière :
        # s'entraîner sur ce qu'on maîtrise déjà ne rapporte rien.
        weak = await graph_engine.recommended_nodes(db, user.id, limit=12)
        targets = [n for n in weak if n.subject == subject][:4]
        target_ids = [n.id for n in targets]
        if not payload.topic:
            node_titles = [n.title for n in targets]

    result = await ai_service.generate_exam(
        user, subject=subject, topic=payload.topic, node_titles=node_titles
    )
    if not result or not result.get("questions"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Aucun sujet exploitable n'a pu être généré. Importe un cours "
                f"en {SUBJECT_LABELS.get(subject, subject)} et réessaie."
            ),
        )

    fmt = format_for(subject)
    questions = [
        ExamQuestion(
            number=int(q.get("number", i + 1)),
            text=str(q.get("text", "")).strip(),
            points=float(q.get("points", 0) or 0),
        )
        for i, q in enumerate(result.get("questions") or [])
        if isinstance(q, dict) and str(q.get("text", "")).strip()
    ]

    return ExamRead(
        subject=subject,
        format=_format_read(subject),
        title=str(result.get("title", "Sujet d'entraînement")),
        instructions=str(result.get("instructions", "")),
        context=str(result.get("context", "")),
        questions=questions,
        duration_minutes=int(result.get("duration_minutes", fmt.duration_minutes)),
        total_points=float(result.get("total_points", fmt.total_points)),
        inspired_by=str(result.get("inspired_by", "")),
        target_node_ids=target_ids,
        has_annales=bool(result.get("_has_annales")),
        sources=[SourceRead.model_validate(s) for s in result.get("_sources", [])],
        model=str(result.get("_model", "")),
        mocked=bool(result.get("_mocked", False)),
    )


@router.post(
    "/evaluate",
    response_model=ExamEvaluationRead,
    summary="Corriger ma copie",
)
async def evaluate_exam(
    payload: ExamEvaluateRequest, user: CurrentUser, db: DbSession
) -> ExamEvaluationRead:
    subject = payload.subject.value

    result = await ai_service.evaluate_exam(
        subject=subject, exercise=payload.exercise, answer=payload.answer
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La correction n'a pas pu être exploitée. Réessaie.",
        )

    fmt = format_for(subject)
    max_score = float(result.get("max_score", fmt.total_points) or fmt.total_points)
    score = max(0.0, min(float(result.get("score", 0) or 0), max_score))

    # ── La boucle de rétroaction ─────────────────────────────────────────
    # Sans elle, rater un BTS blanc n'aurait aucune conséquence : la maîtrise
    # resterait au niveau que les flashcards ont établi, et l'application
    # continuerait à faire réviser autre chose. Or c'est exactement ce cas —
    # bien répondre aux cartes mais rater l'épreuve — qui doit alerter : la
    # notion est reconnue, pas mobilisable.
    ratio = score / max_score if max_score else 0.0
    impacts: list[MasteryImpact] = []
    resurfaced = 0

    target_ids = [
        int(n) for n in (payload.exercise.get("target_node_ids") or []) if n
    ]
    if target_ids:
        nodes = (
            await db.execute(
                select(KnowledgeNode).where(
                    KnowledgeNode.id.in_(target_ids),
                    KnowledgeNode.user_id == user.id,
                )
            )
        ).scalars().all()

        for node in nodes:
            delta = graph_engine.apply_exam_result(node, ratio)
            impacts.append(
                MasteryImpact(
                    node_id=node.id,
                    node_title=node.title,
                    delta=delta,
                    mastery_after=node.mastery,
                )
            )

        # En dessous de la moyenne, les cartes concernées redescendent dans la
        # file. Plus la note est basse, plus le rappel est agressif.
        if ratio < 0.5 and nodes:
            resurfaced = await srs_service.resurface_node_cards(
                db, user.id, [n.id for n in nodes], severity=1.0 - ratio * 2
            )
        await graph_engine.recompute_locks(db, user.id)

    # Une copie rendue est une vraie séance de travail : on la trace, sinon
    # elle n'apparaîtrait ni dans la heatmap ni dans le streak.
    session = StudySession(
        user_id=user.id,
        engine=LearningEngine.chat.value,
        duration_seconds=fmt.duration_minutes * 60,
        cards_reviewed=len(result.get("per_question") or []),
        summary=f"{fmt.label} — {score}/{max_score}",
    )
    db.add(session)
    await srs_service.touch_activity(
        db, user, minutes=fmt.duration_minutes, sessions_count=1
    )
    await db.commit()

    return ExamEvaluationRead(
        score=score,
        max_score=max_score,
        mastery_impact=impacts,
        cards_resurfaced=resurfaced,
        per_question=[
            QuestionFeedback(
                number=int(q.get("number", i + 1)),
                points_earned=float(q.get("points_earned", 0) or 0),
                points_max=float(q.get("points_max", 0) or 0),
                feedback=str(q.get("feedback", "")),
            )
            for i, q in enumerate(result.get("per_question") or [])
            if isinstance(q, dict)
        ],
        criteria_feedback=[
            CriterionFeedback(
                criterion=str(c.get("criterion", "")),
                verdict=str(c.get("verdict", "fragile")),
                comment=str(c.get("comment", "")),
            )
            for c in (result.get("criteria_feedback") or [])
            if isinstance(c, dict) and str(c.get("criterion", "")).strip()
        ],
        strengths=[str(s) for s in (result.get("strengths") or [])],
        gaps=[str(g) for g in (result.get("gaps") or [])],
        next_step=str(result.get("next_step", "")),
        model=str(result.get("_model", "")),
        mocked=bool(result.get("_mocked", False)),
    )


@router.get(
    "/history",
    summary="Mes dernières copies corrigées",
)
async def practice_history(
    user: CurrentUser, db: DbSession, limit: int = 20
) -> list[dict[str, object]]:
    rows = await db.execute(
        select(StudySession)
        .where(
            StudySession.user_id == user.id,
            StudySession.engine == LearningEngine.chat.value,
            StudySession.summary != "",
        )
        .order_by(StudySession.started_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": s.id,
            "date": s.started_at.isoformat(),
            "summary": s.summary,
            "minutes": round(s.duration_seconds / 60),
        }
        for s in rows.scalars().all()
    ]


@router.get("/subjects", summary="Matières entraînables")
async def practice_subjects() -> list[dict[str, str]]:
    return [
        {
            "subject": subject,
            "label": SUBJECT_LABELS.get(subject, subject),
            "exam_label": fmt.label,
        }
        for subject, fmt in EXAM_FORMATS.items()
        if subject in {s.value for s in Subject}
    ]
