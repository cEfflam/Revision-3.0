"""Tests du découpage en chunks — la qualité du RAG commence ici."""

from __future__ import annotations

from app.services.rag.splitter import split_text

COURSE = """# Chapitre 3 — Les jointures

## 3.1 INNER JOIN

La jointure interne ne conserve que les lignes qui trouvent une correspondance
dans les deux tables. C'est la jointure la plus courante.

## 3.2 LEFT JOIN

La jointure externe gauche conserve toutes les lignes de la table de gauche,
avec des NULL quand aucune correspondance n'existe à droite.
"""


def test_sections_carry_breadcrumb_headings() -> None:
    chunks = split_text(COURSE, min_chars=10)
    headings = {c.heading for c in chunks}
    assert "Chapitre 3 — Les jointures > 3.1 INNER JOIN" in headings
    assert "Chapitre 3 — Les jointures > 3.2 LEFT JOIN" in headings


def test_ordinals_are_sequential() -> None:
    chunks = split_text(COURSE, min_chars=10)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_long_section_is_split_with_overlap() -> None:
    body = " ".join(f"Phrase numéro {i} du cours." for i in range(200))
    text = f"# Titre\n\n{body}"
    chunks = split_text(text, max_chars=500, overlap_chars=100, min_chars=10)

    assert len(chunks) > 1
    assert all(len(c.content) <= 500 for c in chunks)
    # Le chevauchement : la fin d'un chunk se retrouve au début du suivant.
    tail = chunks[0].content[-60:]
    assert any(word in chunks[1].content for word in tail.split()[-3:])


def test_empty_text_returns_nothing() -> None:
    assert split_text("") == []
    assert split_text("   \n\n  ") == []


def test_tiny_fragments_are_dropped() -> None:
    text = "# A\n\nok\n\n# B\n\n" + ("Contenu substantiel de section. " * 20)
    chunks = split_text(text, min_chars=80)
    assert all(len(c.content) >= 80 for c in chunks)
