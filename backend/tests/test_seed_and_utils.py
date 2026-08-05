"""Tests du référentiel BTS SIO et des utilitaires."""

from __future__ import annotations

import pytest

from app.core.utils import slugify
from app.models.enums import NodeKind, Subject
from app.services.seed import BTS_SIO_CURRICULUM, NodeSeed, validate_curriculum


def test_builtin_curriculum_is_valid() -> None:
    # Lève une ValueError si un prérequis est inconnu, dupliqué ou déclaré
    # après la notion qui en dépend (ce qui autoriserait un cycle).
    validate_curriculum(BTS_SIO_CURRICULUM)


def test_curriculum_has_cross_subject_dependencies() -> None:
    # Le cœur du produit : Doctrine (dev) doit dépendre de SQL.
    doctrine = next(n for n in BTS_SIO_CURRICULUM if n.slug == "dev-doctrine")
    assert "sql-jointures-internes" in doctrine.prerequisites


def test_validate_rejects_forward_reference() -> None:
    broken = [
        NodeSeed("a", "A", Subject.sql, NodeKind.concept, prerequisites=["b"]),
        NodeSeed("b", "B", Subject.sql, NodeKind.concept),
    ]
    with pytest.raises(ValueError):
        validate_curriculum(broken)


def test_validate_rejects_duplicate_slug() -> None:
    broken = [
        NodeSeed("a", "A", Subject.sql, NodeKind.concept),
        NodeSeed("a", "A bis", Subject.sql, NodeKind.concept),
    ]
    with pytest.raises(ValueError):
        validate_curriculum(broken)


def test_slugify_handles_accents_and_symbols() -> None:
    assert slugify("Jointures SQL (INNER JOIN)") == "jointures-sql-inner-join"
    assert slugify("Révision : clés étrangères !") == "revision-cles-etrangeres"
    assert slugify("   ") == "notion"
