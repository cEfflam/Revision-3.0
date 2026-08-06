"""
Tests de la boucle de rétroaction examen → maîtrise.

Le scénario qui justifie tout ce mécanisme : bien répondre à ses cartes puis
rater le sujet type BTS. C'est le signal le plus précieux du système — la
notion est RECONNUE mais pas MOBILISABLE — et sans cette boucle il serait
purement et simplement ignoré.
"""

from __future__ import annotations

from app.models.enums import NodeStatus
from app.models.graph import KnowledgeNode
from app.services.graph.engine import (
    EXAM_ALPHA,
    MASTERY_ALPHA,
    apply_exam_result,
)


def node(mastery: float, reviews: int = 5) -> KnowledgeNode:
    return KnowledgeNode(
        title="Clé étrangère",
        slug="cle-etrangere",
        mastery=mastery,
        review_count=reviews,
        failure_count=0,
        status=NodeStatus.learning.value,
    )


def test_an_exam_weighs_more_than_a_flashcard() -> None:
    """Réussir une carte prouve qu'on reconnaît ; réussir une épreuve, qu'on sait faire."""
    assert EXAM_ALPHA > MASTERY_ALPHA


def test_failing_an_exam_drops_mastery_sharply() -> None:
    n = node(0.84)
    delta = apply_exam_result(n, 0.0)
    assert delta < 0
    # La chute doit être franche : une baisse cosmétique ne changerait pas les
    # priorités de révision, donc ne servirait à rien.
    assert n.mastery < 0.4
    assert n.failure_count == 1


def test_succeeding_an_exam_raises_mastery() -> None:
    n = node(0.40)
    delta = apply_exam_result(n, 1.0)
    assert delta > 0
    assert n.mastery > 0.40
    assert n.failure_count == 0


def test_an_average_score_barely_moves_a_matching_mastery() -> None:
    """Une note conforme au niveau estimé ne doit pas faire bouger grand-chose."""
    n = node(0.50)
    delta = apply_exam_result(n, 0.50)
    assert abs(delta) < 0.01


def test_mastery_stays_within_bounds() -> None:
    high = node(0.99)
    apply_exam_result(high, 1.0)
    assert 0.0 <= high.mastery <= 1.0

    low = node(0.01)
    apply_exam_result(low, 0.0)
    assert 0.0 <= low.mastery <= 1.0


def test_out_of_range_ratios_are_clamped() -> None:
    n = node(0.5)
    apply_exam_result(n, 2.5)
    assert n.mastery <= 1.0

    other = node(0.5)
    apply_exam_result(other, -3.0)
    assert other.mastery >= 0.0


def test_review_count_grows_so_the_status_can_turn_critical() -> None:
    n = node(0.30, reviews=2)
    apply_exam_result(n, 0.0)
    assert n.review_count == 3
    # Trois passages sous le seuil : la notion bascule en « critique » et
    # remonte d'elle-même en tête des priorités du dashboard.
    assert n.status == NodeStatus.critical.value
