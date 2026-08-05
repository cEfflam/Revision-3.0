"""
Tests du moteur SRS.

Tout est en fonctions pures : aucun mock, aucune base. `fuzz=False` désactive
l'aléa d'intervalle pour rendre chaque assertion exacte.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.enums import CardState, Rating
from app.services.srs.sm2 import (
    DEFAULT_EASE_FACTOR,
    EASY_INTERVAL_DAYS,
    GRADUATING_INTERVAL_DAYS,
    MIN_EASE_FACTOR,
    SrsSnapshot,
    schedule,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def test_new_card_good_enters_learning() -> None:
    update = schedule(SrsSnapshot(), Rating.good, now=NOW, fuzz=False)
    assert update.state is CardState.learning
    # Premier « good » depuis new → étape suivante = 10 minutes.
    assert update.due_at == NOW + timedelta(minutes=10)


def test_two_goods_graduate_to_review() -> None:
    first = schedule(SrsSnapshot(), Rating.good, now=NOW, fuzz=False)
    second = schedule(
        SrsSnapshot(
            state=first.state,
            interval_days=first.interval_days,
            ease_factor=first.ease_factor,
            repetitions=first.repetitions,
        ),
        Rating.good,
        now=NOW,
        fuzz=False,
    )
    assert second.state is CardState.review
    assert second.interval_days == GRADUATING_INTERVAL_DAYS


def test_easy_on_new_card_skips_learning() -> None:
    update = schedule(SrsSnapshot(), Rating.easy, now=NOW, fuzz=False)
    assert update.state is CardState.review
    assert update.interval_days == EASY_INTERVAL_DAYS


def test_review_good_multiplies_by_ease() -> None:
    snapshot = SrsSnapshot(
        state=CardState.review, interval_days=10.0, ease_factor=2.5, repetitions=3
    )
    update = schedule(snapshot, Rating.good, now=NOW, fuzz=False)
    assert update.interval_days == 25.0  # 10 × 2.5
    assert update.repetitions == 4


def test_again_on_review_triggers_relearning_and_lapse() -> None:
    snapshot = SrsSnapshot(
        state=CardState.review, interval_days=20.0, ease_factor=2.5, repetitions=5
    )
    update = schedule(snapshot, Rating.again, now=NOW, fuzz=False)
    assert update.state is CardState.relearning
    assert update.lapses == 1
    # L'intervalle est divisé par deux, pas remis à zéro.
    assert update.interval_days == 10.0
    # L'oubli fait baisser la facilité : la carte reviendra plus souvent.
    assert update.ease_factor < DEFAULT_EASE_FACTOR


def test_ease_never_drops_below_floor() -> None:
    snapshot = SrsSnapshot(
        state=CardState.review, interval_days=5.0, ease_factor=MIN_EASE_FACTOR
    )
    update = schedule(snapshot, Rating.again, now=NOW, fuzz=False)
    assert update.ease_factor == MIN_EASE_FACTOR


def test_relearning_good_returns_to_review() -> None:
    snapshot = SrsSnapshot(
        state=CardState.relearning, interval_days=10.0, ease_factor=2.0, lapses=1
    )
    update = schedule(snapshot, Rating.good, now=NOW, fuzz=False)
    assert update.state is CardState.review
    assert update.interval_days == 10.0
    assert update.lapses == 1
