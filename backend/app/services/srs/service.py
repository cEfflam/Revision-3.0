"""
Orchestration SRS côté base de données.

`sm2.py` calcule, ce fichier persiste. La séparation est volontaire : la
logique pédagogique reste testable sans PostgreSQL, et on pourra remplacer
SM-2 par FSRS en ne touchant qu'un seul appel.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import CardState, Rating
from app.models.graph import KnowledgeNode
from app.models.learning import Card, DailyActivity, ReviewLog
from app.models.user import User
from app.services.graph import engine as graph_engine
from app.services.srs.sm2 import SrsSnapshot, schedule

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
#  File de révision
# ═════════════════════════════════════════════════════════════════════════
async def count_due(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(Card.id)).where(
            Card.user_id == user_id,
            Card.is_suspended.is_(False),
            Card.due_at <= datetime.now(UTC),
        )
    )
    return int(result.scalar_one())


async def get_due_queue(
    db: AsyncSession,
    user_id: int,
    *,
    limit: int = 20,
    subject: str | None = None,
    node_id: int | None = None,
    interleave: bool = True,
) -> list[Card]:
    """
    Cartes à réviser maintenant, dans l'ordre où les présenter.

    `interleave=True` applique l'*interleaving* : on alterne les matières au
    lieu d'enchaîner 20 cartes de SQL. C'est contre-intuitif — ça donne
    l'impression d'apprendre moins bien sur le moment — mais la rétention à
    long terme est nettement supérieure : le cerveau doit à chaque fois
    recharger le bon contexte, et c'est cet effort qui consolide.
    """
    stmt = (
        select(Card)
        .options(selectinload(Card.node))
        .where(
            Card.user_id == user_id,
            Card.is_suspended.is_(False),
            Card.due_at <= datetime.now(UTC),
        )
        # Les cartes en cours d'apprentissage passent avant : leur fenêtre
        # d'efficacité est de quelques minutes, pas de quelques jours.
        .order_by(Card.due_at.asc())
        .limit(limit * 2 if interleave else limit)
    )
    if node_id is not None:
        # Session ciblée sur UNE notion : l'interleaving n'a plus de sens
        # (une seule matière), et il masquerait l'ordre par échéance.
        stmt = stmt.where(Card.node_id == node_id)
        interleave = False
    elif subject:
        stmt = stmt.join(KnowledgeNode, Card.node_id == KnowledgeNode.id).where(
            KnowledgeNode.subject == subject
        )

    cards = list((await db.execute(stmt)).scalars().unique().all())
    if interleave:
        cards = _interleave_by_subject(cards)
    return cards[:limit]


def _interleave_by_subject(cards: list[Card]) -> list[Card]:
    """Round-robin sur les matières : SQL, Anglais, CEJM, SQL, Anglais…"""
    buckets: dict[str, list[Card]] = defaultdict(list)
    for card in cards:
        buckets[card.node.subject if card.node else "_"].append(card)

    mixed: list[Card] = []
    while any(buckets.values()):
        for key in list(buckets):
            if buckets[key]:
                mixed.append(buckets[key].pop(0))
    return mixed


# ═════════════════════════════════════════════════════════════════════════
#  Enregistrement d'une réponse
# ═════════════════════════════════════════════════════════════════════════
async def review(
    db: AsyncSession,
    user: User,
    card: Card,
    rating: Rating,
    *,
    duration_ms: int = 0,
) -> tuple[Card, list[KnowledgeNode]]:
    """
    Applique une réponse : replanifie la carte, journalise, met à jour la
    maîtrise du nœud et l'activité du jour.

    Renvoie la carte à jour et, en cas d'échec, les prérequis fautifs — le
    diagnostic « voilà *pourquoi* tu t'es planté ».

    Ne commit pas : l'endpoint appelant décide du périmètre transactionnel.
    """
    now = datetime.now(UTC)
    snapshot = SrsSnapshot(
        state=CardState(card.state),
        interval_days=card.interval_days,
        ease_factor=card.ease_factor,
        repetitions=card.repetitions,
        lapses=card.lapses,
    )
    elapsed = (
        (now - card.last_reviewed_at).total_seconds() / 86400.0
        if card.last_reviewed_at
        else 0.0
    )

    update = schedule(snapshot, rating, now=now)

    db.add(
        ReviewLog(
            card_id=card.id,
            user_id=user.id,
            rating=rating.value,
            reviewed_at=now,
            elapsed_days=round(elapsed, 4),
            scheduled_days=update.scheduled_days,
            state_before=card.state,
            ease_before=card.ease_factor,
            ease_after=update.ease_factor,
            duration_ms=max(0, duration_ms),
        )
    )

    card.state = update.state.value
    card.interval_days = update.interval_days
    card.ease_factor = update.ease_factor
    card.repetitions = update.repetitions
    card.lapses = update.lapses
    card.due_at = update.due_at
    card.last_reviewed_at = now

    weak: list[KnowledgeNode] = []
    if card.node_id:
        node = await db.get(KnowledgeNode, card.node_id)
        if node:
            graph_engine.apply_review_to_node(node, rating)
            if rating is Rating.again:
                weak = await graph_engine.weak_prerequisites(db, user.id, node.id)

    await touch_activity(db, user, reviews=1)
    return card, weak


# ═════════════════════════════════════════════════════════════════════════
#  Activité quotidienne, streak, heatmap
# ═════════════════════════════════════════════════════════════════════════
async def touch_activity(
    db: AsyncSession,
    user: User,
    *,
    minutes: int = 0,
    reviews: int = 0,
    cards_created: int = 0,
    sessions_count: int = 0,
) -> None:
    """
    Incrémente le compteur du jour (UPSERT atomique) et met à jour le streak.

    `ON CONFLICT DO UPDATE` évite le classique « lire, tester, écrire » qui
    part en doublon dès que deux requêtes arrivent en même temps.
    """
    today = datetime.now(UTC).date()
    xp = reviews * 10 + minutes * 2 + cards_created * 5

    stmt = (
        pg_insert(DailyActivity)
        .values(
            user_id=user.id,
            day=today,
            minutes=minutes,
            reviews=reviews,
            cards_created=cards_created,
            sessions_count=sessions_count,
            xp=xp,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "day"],
            set_={
                "minutes": DailyActivity.minutes + minutes,
                "reviews": DailyActivity.reviews + reviews,
                "cards_created": DailyActivity.cards_created + cards_created,
                "sessions_count": DailyActivity.sessions_count + sessions_count,
                "xp": DailyActivity.xp + xp,
            },
        )
    )
    await db.execute(stmt)
    _bump_streak(user, today)


def _bump_streak(user: User, today: date) -> None:
    last = user.last_active_day
    if last == today:
        return
    # Hier → la série continue. Plus vieux (ou jamais) → elle repart à 1.
    user.streak_current = (
        user.streak_current + 1 if last and (today - last).days == 1 else 1
    )
    user.streak_best = max(user.streak_best, user.streak_current)
    user.last_active_day = today


async def heatmap(
    db: AsyncSession, user_id: int, *, days: int = 365
) -> list[dict[str, int | str]]:
    """Séries quotidiennes pour la heatmap façon GitHub."""
    since = datetime.now(UTC).date() - timedelta(days=days)
    rows = await db.execute(
        select(DailyActivity)
        .where(DailyActivity.user_id == user_id, DailyActivity.day >= since)
        .order_by(DailyActivity.day.asc())
    )
    return [
        {
            "day": a.day.isoformat(),
            "minutes": a.minutes,
            "reviews": a.reviews,
            "xp": a.xp,
        }
        for a in rows.scalars().all()
    ]


async def _count(db: AsyncSession, model, *conditions) -> int:
    stmt = select(func.count(model.id))
    if conditions:
        stmt = stmt.where(*conditions)
    return int((await db.execute(stmt)).scalar_one())


async def review_stats(db: AsyncSession, user_id: int) -> dict[str, int | float]:
    """
    Compteurs du dashboard.

    Plusieurs petits COUNT plutôt qu'un gros SELECT avec agrégats
    conditionnels : sur ces volumes la différence est indétectable, et le code
    reste relisible dans six mois.
    """
    total_cards = await _count(db, Card, Card.user_id == user_id)
    new_cards = await _count(
        db, Card, Card.user_id == user_id, Card.state == CardState.new.value
    )
    # Convention : une carte dont l'intervalle dépasse 3 semaines est acquise.
    mastered = await _count(
        db,
        Card,
        Card.user_id == user_id,
        Card.state == CardState.review.value,
        Card.interval_days >= 21,
    )
    reviews_total = await _count(db, ReviewLog, ReviewLog.user_id == user_id)
    forgotten = await _count(
        db,
        ReviewLog,
        ReviewLog.user_id == user_id,
        ReviewLog.rating == Rating.again.value,
    )

    return {
        "total_cards": total_cards,
        "new_cards": new_cards,
        "mastered_cards": mastered,
        "reviews_total": reviews_total,
        "accuracy": (
            round((reviews_total - forgotten) / reviews_total, 4)
            if reviews_total
            else 0.0
        ),
        "due_now": await count_due(db, user_id),
    }
