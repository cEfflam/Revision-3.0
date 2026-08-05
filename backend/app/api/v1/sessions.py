"""
Sessions d'étude — le « Mode Focus ».

Une session encadre une période de travail : elle démarre quand tu lances le
mode Focus, se termine quand tu arrêtes. C'est elle qui crédite tes minutes
dans l'activité quotidienne (heatmap, streak), et non l'horloge du frontend :
le serveur mesure la durée entre `start` et `end`, ce qui rend le compteur
insensible à un onglet fermé ou à une horloge locale déréglée.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.graph import KnowledgeNode
from app.models.learning import StudySession
from app.schemas.learning import SessionEnd, SessionRead, SessionStart
from app.services.srs import service as srs_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])

# Au-delà de 3 h sans clôture, on considère la session abandonnée : on ne
# créditera que le temps réellement plausible, pas une nuit d'onglet ouvert.
MAX_CREDITED_SECONDS = 3 * 3600


async def _get_owned_session(db, user, session_id: int) -> StudySession:
    session = await db.get(StudySession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable."
        )
    return session


@router.post(
    "/start",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Démarrer une session de travail",
)
async def start_session(
    payload: SessionStart, user: CurrentUser, db: DbSession
) -> SessionRead:
    if payload.node_id is not None:
        node = await db.get(KnowledgeNode, payload.node_id)
        if node is None or node.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Notion introuvable."
            )

    session = StudySession(
        user_id=user.id,
        node_id=payload.node_id,
        engine=payload.engine.value,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionRead.model_validate(session)


@router.post(
    "/{session_id}/end",
    response_model=SessionRead,
    summary="Clôturer une session",
)
async def end_session(
    session_id: int, payload: SessionEnd, user: CurrentUser, db: DbSession
) -> SessionRead:
    session = await _get_owned_session(db, user, session_id)

    # Idempotent : re-clôturer une session déjà fermée ne crédite rien deux fois.
    if session.ended_at is not None:
        return SessionRead.model_validate(session)

    now = datetime.now(UTC)
    elapsed = int((now - session.started_at).total_seconds())
    session.ended_at = now
    session.duration_seconds = max(0, min(elapsed, MAX_CREDITED_SECONDS))
    session.cards_reviewed = payload.cards_reviewed
    session.correct_count = min(payload.correct_count, payload.cards_reviewed)

    minutes = round(session.duration_seconds / 60)
    if minutes:
        await srs_service.touch_activity(
            db, user, minutes=minutes, sessions_count=1
        )
    else:
        await srs_service.touch_activity(db, user, sessions_count=1)

    await db.commit()
    await db.refresh(session)
    return SessionRead.model_validate(session)


@router.get("", response_model=list[SessionRead], summary="Historique des sessions")
async def list_sessions(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=30, ge=1, le=200),
) -> list[SessionRead]:
    rows = await db.execute(
        select(StudySession)
        .where(StudySession.user_id == user.id)
        .order_by(StudySession.started_at.desc())
        .limit(limit)
    )
    return [SessionRead.model_validate(s) for s in rows.scalars().all()]
