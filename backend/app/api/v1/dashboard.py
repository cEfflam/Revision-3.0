"""
Dashboard « Aujourd'hui ».

Le principe de cet écran : il ne montre pas tout ce que l'application sait
faire, il répond à une seule question — **qu'est-ce que je fais maintenant ?**
La liste d'actions est donc calculée côté serveur et ordonnée par priorité,
pas rendue statiquement par le frontend. Si le graphe détecte une régression,
l'action correspondante remonte d'elle-même en tête.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbSession
from app.models.content import Document
from app.models.enums import NodeStatus, Subject
from app.models.graph import KnowledgeNode
from app.models.learning import DailyActivity
from app.models.user import Goal
from app.schemas.graph import NodeRead
from app.schemas.learning import (
    DashboardRead,
    HeatmapPoint,
    StatsRead,
    TodayAction,
)
from app.schemas.onboarding import GoalRead
from app.services.ai import service as ai_service
from app.services.graph import engine as graph_engine
from app.services.srs import service as srs_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Matières dont les épreuves sont rédactionnelles : elles déclenchent l'action
# « défi rédaction » plutôt qu'un exercice technique.
WRITING_SUBJECTS = {Subject.cge.value, Subject.cejm.value}


def _greeting(name: str) -> str:
    hour = datetime.now(UTC).hour
    if hour < 12:
        moment = "Bonjour"
    elif hour < 18:
        moment = "Bon après-midi"
    else:
        moment = "Bonsoir"
    return f"{moment}{f', {name}' if name else ''}"


@router.get("", response_model=DashboardRead, summary="Ma journée")
async def read_dashboard(user: CurrentUser, db: DbSession) -> DashboardRead:
    goal = (
        await db.execute(
            select(Goal).where(Goal.user_id == user.id, Goal.is_primary.is_(True))
        )
    ).scalar_one_or_none()

    due_now = await srs_service.count_due(db, user.id)
    weakest = await graph_engine.recommended_nodes(db, user.id, limit=3)

    # Préparation globale = maîtrise moyenne du graphe. Volontairement simple
    # et honnête : pondérer par la difficulté ou le coefficient d'épreuve
    # donnerait un chiffre plus flatteur mais moins interprétable.
    readiness = float(
        (
            await db.execute(
                select(func.coalesce(func.avg(KnowledgeNode.mastery), 0.0)).where(
                    KnowledgeNode.user_id == user.id
                )
            )
        ).scalar_one()
    )

    today = datetime.now(UTC).date()
    minutes_today = int(
        (
            await db.execute(
                select(func.coalesce(DailyActivity.minutes, 0)).where(
                    DailyActivity.user_id == user.id, DailyActivity.day == today
                )
            )
        ).scalar_one_or_none()
        or 0
    )

    documents_count = int(
        (
            await db.execute(
                select(func.count(Document.id)).where(Document.user_id == user.id)
            )
        ).scalar_one()
    )

    return DashboardRead(
        greeting=_greeting(user.display_name),
        goal=GoalRead.model_validate(goal) if goal else None,
        days_left=(
            (goal.target_date - today).days if goal and goal.target_date else None
        ),
        readiness=round(readiness, 4),
        due_now=due_now,
        daily_minutes=user.daily_minutes,
        streak_current=user.streak_current,
        streak_best=user.streak_best,
        minutes_today=minutes_today,
        actions=_build_actions(
            due_now=due_now,
            weakest=weakest,
            documents_count=documents_count,
            daily_minutes=user.daily_minutes,
        ),
        weakest_nodes=[NodeRead.model_validate(n) for n in weakest],
        heatmap=[
            HeatmapPoint(**point)  # type: ignore[arg-type]
            for point in await srs_service.heatmap(db, user.id, days=365)
        ],
    )


def _build_actions(
    *,
    due_now: int,
    weakest: list[KnowledgeNode],
    documents_count: int,
    daily_minutes: int,
) -> list[TodayAction]:
    """Liste d'actions prioritaires, la plus urgente en premier."""
    actions: list[TodayAction] = []

    # Priorité 1 : les cartes dues. Repousser une révision programmée annule
    # tout le bénéfice de la répétition espacée.
    if due_now:
        actions.append(
            TodayAction(
                key="flashcards",
                icon="layers",
                title="Flashcards du jour",
                subtitle=f"{due_now} carte{'s' if due_now > 1 else ''} à réviser",
                href="/review",
                count=due_now,
                accent="indigo",
            )
        )

    # Priorité 2 : le point faible identifié par le graphe.
    if weakest:
        target = weakest[0]
        critical = target.status == NodeStatus.critical.value
        actions.append(
            TodayAction(
                key="focus",
                icon="target",
                title=f"Session Focus — {target.title}",
                subtitle=(
                    f"Régression détectée ({target.mastery:.0%} de maîtrise)"
                    if critical
                    else f"{target.mastery:.0%} de maîtrise · "
                    f"{min(target.estimated_minutes, daily_minutes)} min"
                ),
                # `focus` lance le chronomètre : une session ciblée sans borne
                # de temps se transforme vite en session sans fin.
                href=f"/review?node={target.id}&focus={min(25, daily_minutes)}",
                accent="rose" if critical else "violet",
            )
        )

    writing_target = next(
        (n for n in weakest if n.subject in WRITING_SUBJECTS), None
    )
    if writing_target:
        actions.append(
            TodayAction(
                key="writing",
                icon="pen-line",
                title="Défi rédaction",
                subtitle=f"Cas pratique ou synthèse — {writing_target.title}",
                href="/writing",
                accent="amber",
            )
        )

    # Sans documents, tout le reste tourne à vide : c'est LA première action.
    if documents_count == 0:
        actions.insert(
            0,
            TodayAction(
                key="import",
                icon="upload",
                title="Importe ton premier cours",
                subtitle="PDF, Word ou Markdown — l'app en tire fiches et cartes",
                href="/brain",
                accent="emerald",
            ),
        )

    if not actions:
        actions.append(
            TodayAction(
                key="explore",
                icon="compass",
                title="Rien d'urgent aujourd'hui",
                subtitle="Explore ton arbre de compétences et ouvre une notion",
                href="/roadmap",
                accent="slate",
            )
        )
    return actions


@router.get("/stats", response_model=StatsRead, summary="Statistiques globales")
async def read_stats(user: CurrentUser, db: DbSession) -> StatsRead:
    base = await srs_service.review_stats(db, user.id)

    nodes_total = int(
        (
            await db.execute(
                select(func.count(KnowledgeNode.id)).where(
                    KnowledgeNode.user_id == user.id
                )
            )
        ).scalar_one()
    )
    nodes_mastered = int(
        (
            await db.execute(
                select(func.count(KnowledgeNode.id)).where(
                    KnowledgeNode.user_id == user.id,
                    KnowledgeNode.status == NodeStatus.mastered.value,
                )
            )
        ).scalar_one()
    )
    documents_total = int(
        (
            await db.execute(
                select(func.count(Document.id)).where(Document.user_id == user.id)
            )
        ).scalar_one()
    )

    # Maîtrise moyenne par matière : c'est la « carte des compétences » avec ses
    # barres de progression, pas une note globale qui masque les écarts.
    rows = await db.execute(
        select(KnowledgeNode.subject, func.avg(KnowledgeNode.mastery))
        .where(KnowledgeNode.user_id == user.id)
        .group_by(KnowledgeNode.subject)
    )
    subject_mastery = {
        subject: round(float(average or 0.0), 4) for subject, average in rows.all()
    }

    return StatsRead(
        **base,  # type: ignore[arg-type]
        nodes_total=nodes_total,
        nodes_mastered=nodes_mastered,
        documents_total=documents_total,
        subject_mastery=subject_mastery,
    )


@router.get(
    "/heatmap", response_model=list[HeatmapPoint], summary="Heatmap de régularité"
)
async def read_heatmap(
    user: CurrentUser,
    db: DbSession,
    days: int = Query(default=365, ge=7, le=730),
) -> list[HeatmapPoint]:
    return [
        HeatmapPoint(**point)  # type: ignore[arg-type]
        for point in await srs_service.heatmap(db, user.id, days=days)
    ]


@router.post("/journal", summary="Générer le journal du soir")
async def generate_journal(user: CurrentUser, db: DbSession) -> dict[str, str]:
    """
    Résumé de la journée rédigé par l'IA, stocké sur l'activité du jour.

    C'est la boucle de feedback : voir écrit noir sur blanc « tu as corrigé une
    erreur que tu répétais depuis trois semaines » fait plus pour la motivation
    qu'un compteur de points.
    """
    today = datetime.now(UTC).date()
    activity = (
        await db.execute(
            select(DailyActivity).where(
                DailyActivity.user_id == user.id, DailyActivity.day == today
            )
        )
    ).scalar_one_or_none()

    if activity is None:
        return {
            "journal": "Aucune activité enregistrée aujourd'hui. "
            "Lance une session, même de 10 minutes.",
            "day": today.isoformat(),
        }

    weakest = await graph_engine.recommended_nodes(db, user.id, limit=3)
    stats = {
        "cartes révisées": activity.reviews,
        "minutes travaillées": activity.minutes,
        "cartes créées": activity.cards_created,
        "série en cours (jours)": user.streak_current,
        "notions fragiles": ", ".join(f"{n.title} ({n.mastery:.0%})" for n in weakest)
        or "aucune",
    }

    activity.journal = await ai_service.write_journal(stats)
    await db.commit()
    return {"journal": activity.journal, "day": today.isoformat()}
