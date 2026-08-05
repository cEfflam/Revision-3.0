"""
Moteur de répétition espacée — SM-2, variante Anki.

═══════════════════════════════════════════════════════════════════════════
POURQUOI ÇA MARCHE
═══════════════════════════════════════════════════════════════════════════
La courbe de l'oubli (Ebbinghaus) est exponentielle : on oublie très vite,
puis de plus en plus lentement. Réviser trop tôt est du temps perdu ; réviser
trop tard oblige à réapprendre depuis zéro. Le point optimal est juste avant
l'oubli — c'est ce moment que cet algorithme estime.

═══════════════════════════════════════════════════════════════════════════
LES TROIS VARIABLES
═══════════════════════════════════════════════════════════════════════════
  ease_factor    Facilité perçue de la carte. Démarre à 2.5 : chaque succès
                 multiplie l'intervalle par 2.5. Un échec la fait baisser,
                 donc la carte revient plus souvent. Plancher à 1.3, sinon
                 une carte difficile disparaîtrait du planning.
  interval_days  Délai jusqu'à la prochaine présentation.
  repetitions    Succès consécutifs. En phase d'apprentissage, sert aussi
                 d'index d'étape — ce qui évite une colonne supplémentaire.

═══════════════════════════════════════════════════════════════════════════
LES QUATRE ÉTATS
═══════════════════════════════════════════════════════════════════════════
  new         Jamais vue.
  learning    Vue à l'instant, en cours d'ancrage (minutes).
  review      Ancrée, révisée à intervalles longs (jours).
  relearning  Oubliée après avoir été ancrée : on repasse par des minutes.

═══════════════════════════════════════════════════════════════════════════
ÉVOLUTION VERS FSRS
═══════════════════════════════════════════════════════════════════════════
SM-2 est un excellent point de départ : lisible, éprouvé, ~100 lignes. FSRS
est plus précis (il modélise stabilité et difficulté séparément et s'entraîne
sur ton historique) mais demande des poids calibrés. C'est possible plus tard
*sans perte de données* : `ReviewLog` conserve chaque réponse, donc FSRS
pourra être entraîné rétroactivement sur ton passé. Il suffira d'ajouter
`fsrs.py` à côté et de basculer l'appel dans `service.py`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.models.enums import CardState, Rating

# ── Paramètres réglables ─────────────────────────────────────────────────
# Étapes d'apprentissage, en minutes. Deux paliers : un rappel immédiat pour
# fixer la trace, un second à 10 min pour vérifier qu'elle tient.
LEARNING_STEPS_MINUTES: tuple[int, ...] = (1, 10)
RELEARNING_STEPS_MINUTES: tuple[int, ...] = (10,)

GRADUATING_INTERVAL_DAYS = 1.0   # première révision après validation
EASY_INTERVAL_DAYS = 4.0         # raccourci si la carte est jugée « facile »

MIN_EASE_FACTOR = 1.3
MAX_EASE_FACTOR = 3.0
DEFAULT_EASE_FACTOR = 2.5

EASE_DELTA: dict[Rating, float] = {
    Rating.again: -0.20,
    Rating.hard: -0.15,
    Rating.good: 0.0,
    Rating.easy: +0.15,
}

HARD_INTERVAL_MULTIPLIER = 1.2
EASY_INTERVAL_BONUS = 1.3
# Après un oubli, on ne repart pas de zéro : la trace résiduelle justifie de
# garder la moitié de l'intervalle précédent.
LAPSE_INTERVAL_MULTIPLIER = 0.5
MAX_INTERVAL_DAYS = 365.0 * 3
# ±5 % d'aléa pour éviter que 80 cartes apprises le même jour ne retombent
# toutes ensemble trois semaines plus tard.
FUZZ_RATIO = 0.05


@dataclass(frozen=True, slots=True)
class SrsSnapshot:
    """État SRS d'une carte, en entrée de l'algorithme."""

    state: CardState = CardState.new
    interval_days: float = 0.0
    ease_factor: float = DEFAULT_EASE_FACTOR
    repetitions: int = 0
    lapses: int = 0


@dataclass(frozen=True, slots=True)
class SrsUpdate:
    """Nouvel état calculé + date de la prochaine présentation."""

    state: CardState
    interval_days: float
    ease_factor: float
    repetitions: int
    lapses: int
    due_at: datetime

    @property
    def scheduled_days(self) -> float:
        return self.interval_days


def _clamp_ease(value: float) -> float:
    return max(MIN_EASE_FACTOR, min(MAX_EASE_FACTOR, value))


def _apply_fuzz(days: float, *, enabled: bool) -> float:
    if not enabled or days < 2.0:
        return days
    delta = days * FUZZ_RATIO
    return max(1.0, days + random.uniform(-delta, delta))


def _cap(days: float) -> float:
    return min(MAX_INTERVAL_DAYS, round(days, 4))


def schedule(
    snapshot: SrsSnapshot,
    rating: Rating,
    *,
    now: datetime | None = None,
    fuzz: bool = True,
) -> SrsUpdate:
    """
    Calcule le prochain rendez-vous d'une carte.

    Fonction pure : mêmes entrées → mêmes sorties (à l'aléa près, désactivable
    via `fuzz=False` pour les tests). Elle ne touche ni la base ni la carte ;
    c'est `service.py` qui persiste le résultat.
    """
    now = now or datetime.now(UTC)
    ease = _clamp_ease(snapshot.ease_factor + EASE_DELTA[rating])

    # ── Phases courtes : on raisonne en minutes ──────────────────────────
    if snapshot.state in (CardState.new, CardState.learning):
        steps = LEARNING_STEPS_MINUTES
        # En apprentissage, `repetitions` = index de l'étape atteinte.
        step = snapshot.repetitions if snapshot.state == CardState.learning else 0

        if rating is Rating.easy:
            return _graduate(snapshot, ease, EASY_INTERVAL_DAYS, now, fuzz=fuzz)

        if rating is Rating.again:
            step = 0
        elif rating is Rating.hard:
            step = min(step, len(steps) - 1)
        else:  # good → on avance d'un palier
            step += 1
            if step >= len(steps):
                return _graduate(
                    snapshot, ease, GRADUATING_INTERVAL_DAYS, now, fuzz=fuzz
                )

        return SrsUpdate(
            state=CardState.learning,
            interval_days=steps[step] / 1440.0,
            ease_factor=ease,
            repetitions=step,
            lapses=snapshot.lapses,
            due_at=now + timedelta(minutes=steps[step]),
        )

    # ── Carte oubliée alors qu'elle était acquise ────────────────────────
    if snapshot.state is CardState.review and rating is Rating.again:
        reduced = max(1.0, snapshot.interval_days * LAPSE_INTERVAL_MULTIPLIER)
        return SrsUpdate(
            state=CardState.relearning,
            interval_days=_cap(reduced),
            ease_factor=ease,
            repetitions=0,
            lapses=snapshot.lapses + 1,
            due_at=now + timedelta(minutes=RELEARNING_STEPS_MINUTES[0]),
        )

    # ── Réapprentissage en cours ─────────────────────────────────────────
    if snapshot.state is CardState.relearning:
        if rating is Rating.again:
            return SrsUpdate(
                state=CardState.relearning,
                interval_days=snapshot.interval_days,
                ease_factor=ease,
                repetitions=0,
                lapses=snapshot.lapses,
                due_at=now + timedelta(minutes=RELEARNING_STEPS_MINUTES[0]),
            )
        if rating is Rating.hard:
            minutes = int(RELEARNING_STEPS_MINUTES[0] * 1.5)
            return SrsUpdate(
                state=CardState.relearning,
                interval_days=snapshot.interval_days,
                ease_factor=ease,
                repetitions=0,
                lapses=snapshot.lapses,
                due_at=now + timedelta(minutes=minutes),
            )
        # good / easy → retour en révision longue, sur l'intervalle réduit
        days = _apply_fuzz(max(1.0, snapshot.interval_days), enabled=fuzz)
        return SrsUpdate(
            state=CardState.review,
            interval_days=_cap(days),
            ease_factor=ease,
            repetitions=1,
            lapses=snapshot.lapses,
            due_at=now + timedelta(days=days),
        )

    # ── Révision normale (state == review, rating != again) ──────────────
    base = max(1.0, snapshot.interval_days)
    if rating is Rating.hard:
        days = base * HARD_INTERVAL_MULTIPLIER
    elif rating is Rating.good:
        days = base * ease
    else:  # easy
        days = base * ease * EASY_INTERVAL_BONUS

    days = _apply_fuzz(days, enabled=fuzz)
    return SrsUpdate(
        state=CardState.review,
        interval_days=_cap(days),
        ease_factor=ease,
        repetitions=snapshot.repetitions + 1,
        lapses=snapshot.lapses,
        due_at=now + timedelta(days=days),
    )


def _graduate(
    snapshot: SrsSnapshot,
    ease: float,
    interval_days: float,
    now: datetime,
    *,
    fuzz: bool,
) -> SrsUpdate:
    """Sortie de la phase d'apprentissage : la carte passe en révision."""
    days = _apply_fuzz(interval_days, enabled=fuzz)
    return SrsUpdate(
        state=CardState.review,
        interval_days=_cap(days),
        ease_factor=ease,
        repetitions=1,
        lapses=snapshot.lapses,
        due_at=now + timedelta(days=days),
    )


def retention_estimate(interval_days: float, elapsed_days: float) -> float:
    """
    Probabilité estimée de se souvenir, d'après la courbe de l'oubli
    R = exp(-t / S). Utilisé pour l'affichage (« 68 % de rétention »), pas
    pour la planification.
    """
    if interval_days <= 0:
        return 0.0
    import math

    return round(math.exp(-max(0.0, elapsed_days) / interval_days), 4)
