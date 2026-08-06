"""
Tests du rapprochement des notions avec le graphe.

Le scénario redouté, et la raison d'être de ce module : importer trois fiches
contenant « Algèbre de Boole » ne doit créer qu'UNE notion. Sans ça, chaque
variante orthographique devient un nœud avec sa propre maîtrise, et le graphe
cesse de vouloir dire quoi que ce soit.
"""

from __future__ import annotations

from app.models.graph import KnowledgeNode
from app.services.graph.matcher import (
    CERTAIN_THRESHOLD,
    extract_candidates,
    match_title,
    normalise,
)


def node(title: str, slug: str = "") -> KnowledgeNode:
    return KnowledgeNode(title=title, slug=slug or title.lower().replace(" ", "-"))


# ── Normalisation ────────────────────────────────────────────────────────
def test_accents_articles_and_case_are_neutralised() -> None:
    assert normalise("L'algèbre de Boole") == normalise("Algebre de boole")
    assert normalise("ALGÈBRE DE BOOLE") == normalise("algèbre de Boole")


def test_filler_words_are_removed() -> None:
    # « Introduction à l'algèbre de Boole » doit rejoindre « Algèbre de Boole ».
    assert normalise("Introduction à l'algèbre de Boole") == "algebre-boole"
    assert normalise("Cours : Algèbre de Boole") == "algebre-boole"


# ── Rapprochement ────────────────────────────────────────────────────────
def test_orthographic_variants_match_with_certainty() -> None:
    graph = [node("Algèbre de Boole")]
    for variant in ("Algebre de boole", "L'ALGÈBRE DE BOOLE", "algèbre de Boole"):
        match = match_title(variant, graph)
        assert match.verdict == "certain", variant
        assert match.node is graph[0]
        assert match.score >= CERTAIN_THRESHOLD


def test_extended_title_matches_the_shorter_notion() -> None:
    graph = [node("Algèbre de Boole")]
    match = match_title("Introduction à l'algèbre de Boole", graph)
    assert match.verdict == "certain"
    assert match.node is graph[0]


def test_unrelated_title_creates_a_new_notion() -> None:
    graph = [node("Algèbre de Boole"), node("INNER JOIN")]
    match = match_title("Les sept couches du modèle OSI", graph)
    assert match.verdict == "new"
    assert match.node is None


def test_empty_graph_always_yields_new() -> None:
    assert match_title("Algèbre de Boole", []).verdict == "new"


def test_close_but_uncertain_titles_are_only_suggested() -> None:
    """Entre les deux seuils, on ne décide pas : l'utilisateur tranche."""
    graph = [node("INNER JOIN", slug="sql-jointures-internes")]
    match = match_title("Rappel sur les jointures internes", graph)
    assert match.verdict == "suggested"
    assert match.node is graph[0]


# ── Extraction depuis les titres de section ──────────────────────────────
def test_last_meaningful_segment_becomes_the_notion() -> None:
    candidates = extract_candidates(
        ["Modèle OSI > Les sept couches du modèle"]
    )
    assert candidates[0].title == "Les sept couches du modèle"
    # Le chemin complet est conservé : c'est le parent qui porte la matière.
    assert "Modèle OSI" in candidates[0].breadcrumb


def test_structural_headings_are_ignored() -> None:
    candidates = extract_candidates(
        ["Sommaire", "Préambule", "Table des matières", "Remerciements"]
    )
    assert candidates == []


def test_generic_leaf_falls_back_to_its_parent() -> None:
    candidates = extract_candidates(["Algèbre de Boole > Introduction"])
    assert candidates[0].title == "Algèbre de Boole"


def test_duplicates_are_collapsed() -> None:
    candidates = extract_candidates(
        [
            "Chapitre 1 > Algèbre de Boole",
            "Chapitre 3 > L'algèbre de Boole",
            "Annexe > ALGEBRE DE BOOLE",
        ]
    )
    assert len(candidates) == 1


def test_candidate_count_is_capped() -> None:
    headings = [f"Chapitre {i} > Notion numéro {i}" for i in range(200)]
    assert len(extract_candidates(headings, max_titles=25)) == 25
