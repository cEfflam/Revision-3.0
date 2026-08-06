"""
Générateur de parcours d'apprentissage.

La dernière « killer feature » du cahier des charges : tu donnes un objectif,
l'application construit un chemin ordonné pour y arriver.

Ce qui le distingue d'un plan de cours trouvé sur internet, c'est qu'il est
alimenté par TES données — le niveau que tu as déclaré, et surtout les notions
que le graphe a mesurées comme fragiles. Sans ces deux entrées, le modèle
produirait un programme générique.

Le parcours est persisté : on le suit sur des semaines, on coche les étapes.
Le régénérer à chaque affichage coûterait un appel de modèle par ouverture
d'écran, pour un contenu qui ne bouge pas.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.core.deps import CurrentUser, DbSession
from app.models.enums import Subject
from app.models.graph import KnowledgeNode
from app.models.user import Goal, RoadmapStep, SelfAssessment
from app.schemas.roadmap import (
    RoadmapGenerateRequest,
    RoadmapRead,
    RoadmapStepRead,
    RoadmapStepUpdate,
)
from app.services.ai import service as ai_service
from app.services.graph import engine as graph_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/roadmap", tags=["roadmap"])

VALID_SUBJECTS = {s.value for s in Subject}


@router.get("", response_model=RoadmapRead, summary="Mon parcours")
async def read_roadmap(user: CurrentUser, db: DbSession) -> RoadmapRead:
    steps = (
        await db.execute(
            select(RoadmapStep)
            .where(RoadmapStep.user_id == user.id)
            .order_by(RoadmapStep.order_index)
        )
    ).scalars().all()

    goal = (
        await db.execute(
            select(Goal).where(Goal.user_id == user.id, Goal.is_primary.is_(True))
        )
    ).scalar_one_or_none()

    total_minutes = sum(s.estimated_minutes for s in steps)
    return RoadmapRead(
        objective=goal.title if goal else "",
        total_estimated_hours=round(total_minutes / 60, 1),
        steps=[RoadmapStepRead.model_validate(s) for s in steps],
        generated_at=steps[0].created_at if steps else None,
    )


@router.post(
    "/generate",
    response_model=RoadmapRead,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un parcours vers mon objectif",
)
async def generate_roadmap(
    payload: RoadmapGenerateRequest, user: CurrentUser, db: DbSession
) -> RoadmapRead:
    goal = (
        await db.get(Goal, payload.goal_id)
        if payload.goal_id
        else (
            await db.execute(
                select(Goal).where(Goal.user_id == user.id, Goal.is_primary.is_(True))
            )
        ).scalar_one_or_none()
    )
    if goal is None or goal.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun objectif défini. Passe d'abord par l'onboarding.",
        )

    existing = (
        await db.execute(
            select(RoadmapStep.id).where(RoadmapStep.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if existing and not payload.replace:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un parcours existe déjà. Relance avec replace=true pour l'écraser.",
        )

    # ── Les données qui font la différence ───────────────────────────────
    levels = {
        row.subject: row.level
        for row in (
            await db.execute(
                select(SelfAssessment).where(SelfAssessment.user_id == user.id)
            )
        ).scalars()
    }
    weak = await graph_engine.recommended_nodes(db, user.id, limit=10)
    weak_labels = [f"{n.title} ({n.mastery:.0%})" for n in weak]

    result = await ai_service.generate_roadmap(
        objective=goal.title,
        target_date=goal.target_date.isoformat() if goal.target_date else None,
        daily_minutes=goal.daily_minutes or user.daily_minutes,
        levels=levels,
        weak_nodes=weak_labels,
        max_steps=payload.max_steps,
    )
    raw_steps = result.get("steps") if isinstance(result, dict) else None
    if not raw_steps:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'IA n'a produit aucun parcours exploitable. Réessaie.",
        )

    # Association des étapes aux notions existantes du graphe, par titre.
    nodes = (
        await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.user_id == user.id)
        )
    ).scalars().all()
    by_title = {n.title.strip().lower(): n for n in nodes}

    if existing:
        await db.execute(delete(RoadmapStep).where(RoadmapStep.user_id == user.id))

    created: list[RoadmapStep] = []
    for index, raw in enumerate(raw_steps[: payload.max_steps]):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        subject = str(raw.get("subject", Subject.other.value)).strip()
        prerequisites = raw.get("prerequisites") or []
        node = by_title.get(title.lower())

        step = RoadmapStep(
            user_id=user.id,
            goal_id=goal.id,
            node_id=node.id if node else None,
            order_index=int(raw.get("order", index + 1)),
            title=title[:200],
            subject=subject if subject in VALID_SUBJECTS else Subject.other.value,
            estimated_minutes=max(10, int(raw.get("estimated_minutes", 60) or 60)),
            why=str(raw.get("why", "")).strip(),
            prerequisites=" | ".join(str(p) for p in prerequisites if str(p).strip()),
        )
        db.add(step)
        created.append(step)

    if not created:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Aucune étape valide dans la réponse de l'IA.",
        )

    await db.commit()
    for step in created:
        await db.refresh(step)

    created.sort(key=lambda s: s.order_index)
    total_minutes = sum(s.estimated_minutes for s in created)
    logger.info("Parcours généré : %s étapes pour l'utilisateur %s", len(created), user.id)

    return RoadmapRead(
        objective=str(result.get("objective") or goal.title),
        feasible=bool(result.get("feasible", True)),
        advice=str(result.get("advice", "")),
        total_estimated_hours=round(total_minutes / 60, 1),
        steps=[RoadmapStepRead.model_validate(s) for s in created],
        generated_at=created[0].created_at,
        model=str(result.get("_model", "")),
        mocked=bool(result.get("_mocked", False)),
    )


@router.patch(
    "/steps/{step_id}",
    response_model=RoadmapStepRead,
    summary="Cocher une étape",
)
async def update_step(
    step_id: int, payload: RoadmapStepUpdate, user: CurrentUser, db: DbSession
) -> RoadmapStepRead:
    step = await db.get(RoadmapStep, step_id)
    if step is None or step.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Étape introuvable."
        )
    step.is_done = payload.is_done
    step.completed_at = datetime.now(UTC) if payload.is_done else None
    await db.commit()
    await db.refresh(step)
    return RoadmapStepRead.model_validate(step)


@router.delete(
    "", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer mon parcours"
)
async def delete_roadmap(user: CurrentUser, db: DbSession) -> None:
    await db.execute(delete(RoadmapStep).where(RoadmapStep.user_id == user.id))
    await db.commit()
