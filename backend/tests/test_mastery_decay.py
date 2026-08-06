"""
Tests de la décroissance de maîtrise dans le temps.

Le trou que ces tests ferment : la maîtrise stockée est un instantané. Sans
décroissance, une notion validée il y a six mois reste affichée à 90 % et
n'est jamais reproposée — alors que c'est précisément celle qu'on a oubliée.

Le SRS gère l'oubli au niveau des CARTES ; rien ne le gérait au niveau des
NOTIONS.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.graph import KnowledgeNode
from app.services.graph.engine import (
    MASTERY_HALF_LIFE_DAYS,
    effective_mastery,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def node(mastery: float, days_ago: float | None) -> KnowledgeNode:
    return KnowledgeNode(
        title="Algèbre de Boole",
        slug="algebre-de-boole",
        mastery=mastery,
        last_studied_at=(
            NOW - timedelta(days=days_ago) if days_ago is not None else None
        ),
    )


def test_a_notion_revised_today_keeps_its_mastery() -> None:
    assert effective_mastery(node(0.80, 0), NOW) == 0.80


def test_mastery_halves_after_one_half_life() -> None:
    result = effective_mastery(node(0.80, MASTERY_HALF_LIFE_DAYS), NOW)
    assert 0.28 < result < 0.32  # 0.80 × e⁻¹ ≈ 0.294


def test_an_old_strong_notion_falls_below_a_recent_weaker_one() -> None:
    """Le cas qui justifie tout : 85 % il y a six mois vaut moins que 70 % hier."""
    ancienne = effective_mastery(node(0.85, 180), NOW)
    recente = effective_mastery(node(0.70, 1), NOW)
    assert ancienne < recente


def test_a_never_studied_notion_is_untouched() -> None:
    # Une maîtrise déclarée à l'onboarding, sans séance : rien à faire décroître.
    assert effective_mastery(node(0.40, None), NOW) == 0.40


def test_zero_mastery_stays_zero() -> None:
    assert effective_mastery(node(0.0, 300), NOW) == 0.0


def test_decay_never_goes_negative() -> None:
    assert effective_mastery(node(0.95, 3650), NOW) >= 0.0


def test_a_future_date_does_not_increase_mastery() -> None:
    """Garde-fou contre une horloge décalée."""
    assert effective_mastery(node(0.60, -30), NOW) == 0.60
