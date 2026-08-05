"""
Onboarding — la première chose que fait l'utilisateur.

En une requête : l'objectif est enregistré, le niveau déclaré par matière est
sauvegardé, et le graphe de compétences BTS SIO est instancié avec une maîtrise
initiale cohérente. À la fin de l'appel, l'application a de quoi proposer une
séance pertinente dès la première ouverture du dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update

from app.core.deps import CurrentUser, DbSession
from app.models.user import Goal, SelfAssessment
from app.schemas.onboarding import (
    AssessmentRead,
    GoalRead,
    OnboardingRequest,
    OnboardingResponse,
)
from app.services.seed import seed_curriculum

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Configurer objectif, niveau et temps disponible",
)
async def complete_onboarding(
    payload: OnboardingRequest, user: CurrentUser, db: DbSession
) -> OnboardingResponse:
    # Un seul objectif principal : les précédents sont rétrogradés.
    await db.execute(
        update(Goal)
        .where(Goal.user_id == user.id, Goal.is_primary.is_(True))
        .values(is_primary=False)
    )

    goal = Goal(
        user_id=user.id,
        title=payload.goal.title.strip(),
        kind=payload.goal.kind.value,
        description=payload.goal.description.strip(),
        target_date=payload.goal.target_date,
        daily_minutes=payload.daily_minutes,
        is_primary=True,
        is_active=True,
    )
    db.add(goal)

    # Les auto-évaluations sont remplacées, pas accumulées : un second passage
    # dans l'onboarding doit corriger les niveaux, pas en créer des doublons.
    existing = {
        assessment.subject: assessment
        for assessment in (
            await db.execute(
                select(SelfAssessment).where(SelfAssessment.user_id == user.id)
            )
        )
        .scalars()
        .all()
    }
    levels: dict[str, int] = {}
    for item in payload.assessments:
        levels[item.subject.value] = item.level
        current = existing.get(item.subject.value)
        if current:
            current.level = item.level
        else:
            db.add(
                SelfAssessment(
                    user_id=user.id, subject=item.subject.value, level=item.level
                )
            )

    user.daily_minutes = payload.daily_minutes
    user.onboarding_completed = True

    await db.flush()
    nodes_created = await seed_curriculum(db, user, assessments=levels)

    await db.commit()
    await db.refresh(goal)

    assessments = (
        await db.execute(
            select(SelfAssessment)
            .where(SelfAssessment.user_id == user.id)
            .order_by(SelfAssessment.subject)
        )
    ).scalars().all()

    message = (
        f"Objectif enregistré. {nodes_created} compétences ajoutées à ton graphe."
        if nodes_created
        else "Objectif mis à jour. Ton graphe de compétences était déjà en place."
    )
    return OnboardingResponse(
        goal=GoalRead.model_validate(goal),
        assessments=[AssessmentRead.model_validate(a) for a in assessments],
        nodes_created=nodes_created,
        message=message,
    )


@router.get("/goal", response_model=GoalRead, summary="Objectif principal")
async def read_primary_goal(user: CurrentUser, db: DbSession) -> GoalRead:
    goal = (
        await db.execute(
            select(Goal).where(Goal.user_id == user.id, Goal.is_primary.is_(True))
        )
    ).scalar_one_or_none()
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun objectif défini. Passe par l'onboarding.",
        )
    return GoalRead.model_validate(goal)
