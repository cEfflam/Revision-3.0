"""
Rapprochement des notions d'un document avec le graphe existant.

LE PROBLÈME RÉSOLU ICI
──────────────────────
Tu importes une fiche de révision qui contient « Algèbre de Boole ». Ton
graphe contient peut-être déjà « L'algèbre de Boole », ou « Algebre de
boole », ou rien du tout. Sans rapprochement, chaque import crée un nouveau
nœud : au bout de trois documents tu as quatre fois la même notion, chacune
avec sa propre maîtrise, et le graphe ne veut plus rien dire.

LA MÉTHODE
──────────
Trois passes, de la plus sûre à la plus permissive :

  1. SLUG IDENTIQUE — « L'algèbre de Boole » et « Algebre de Boole » donnent
     tous deux `algebre-de-boole`. Accents, articles, ponctuation et casse
     disparaissent. C'est le cas le plus fréquent et il est certain.
  2. INCLUSION — « Introduction à l'algèbre de Boole » contient le slug
     `algebre-de-boole`. Un titre de section est souvent une paraphrase
     étendue d'une notion existante.
  3. SIMILARITÉ — distance d'édition sur les slugs, pour rattraper les
     fautes de frappe et les variantes de formulation.

En dessous du seuil de certitude, on ne décide pas : la proposition remonte
à l'utilisateur, qui tranche. Un graphe faux est pire qu'un graphe incomplet,
parce qu'il oriente les révisions vers de mauvaises notions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.core.utils import slugify
from app.models.graph import KnowledgeNode

#: Au-dessus : on rattache sans demander. Réglé haut volontairement — une
#: fusion abusive est invisible et difficile à défaire.
CERTAIN_THRESHOLD = 0.88
#: Au-dessus : on propose, l'utilisateur confirme.
SUGGEST_THRESHOLD = 0.62

#: Mots vides qui parasitent la comparaison. « Introduction à X » et « X »
#: doivent se rapprocher ; « le », « la », « les » ne portent aucun sens.
_STOPWORDS = {
    "le", "la", "les", "l", "de", "du", "des", "d", "un", "une", "et", "a",
    "au", "aux", "en", "the", "of", "introduction", "notions", "notion",
    "cours", "chapitre", "partie", "fiche", "revision", "generalites",
}


@dataclass(slots=True)
class NodeMatch:
    """Résultat du rapprochement d'un titre candidat."""

    title: str
    node: KnowledgeNode | None
    score: float
    #: "certain" | "suggested" | "new"
    verdict: str

    @property
    def is_new(self) -> bool:
        return self.node is None


def normalise(title: str) -> str:
    """
    « Introduction à l'algèbre de Boole » → « algebre-boole ».

    On retire les mots vides APRÈS la mise en slug : c'est ce qui permet à un
    titre de section et à une notion de se rejoindre.
    """
    slug = slugify(title)
    tokens = [t for t in slug.split("-") if t and t not in _STOPWORDS]
    return "-".join(tokens) or slug


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    # Inclusion : « algebre-boole » dans « introduction-algebre-boole ».
    if left in right or right in left:
        shorter, longer = sorted((left, right), key=len)
        return 0.90 + 0.09 * (len(shorter) / len(longer))
    return SequenceMatcher(None, left, right).ratio()


def match_title(title: str, nodes: list[KnowledgeNode]) -> NodeMatch:
    """Rapproche un titre candidat du meilleur nœud existant."""
    candidate = normalise(title)
    best: KnowledgeNode | None = None
    best_score = 0.0

    for node in nodes:
        for reference in (normalise(node.title), normalise(node.slug)):
            score = _similarity(candidate, reference)
            if score > best_score:
                best, best_score = node, score

    if best_score >= CERTAIN_THRESHOLD:
        return NodeMatch(title, best, round(best_score, 3), "certain")
    if best_score >= SUGGEST_THRESHOLD:
        return NodeMatch(title, best, round(best_score, 3), "suggested")
    return NodeMatch(title, None, round(best_score, 3), "new")


#: Titres à ignorer : ils structurent le document sans désigner de notion.
_NOISE_RE = re.compile(
    r"^(sommaire|table des mati|pr[ée]ambule|introduction|conclusion|"
    r"remerciements?|le mot du|contenu du|avant.propos|annexes?|bibliographie)",
    flags=re.IGNORECASE,
)


@dataclass(slots=True)
class Candidate:
    """Une notion détectée, avec le chemin complet qui l'a produite."""

    title: str
    #: Fil d'Ariane d'origine, ex. « Modèle OSI > Les sept couches ».
    #: Conservé parce que le PARENT porte souvent la matière : « les sept
    #: couches du modèle » ne dit rien, « Modèle OSI » dit « réseau ».
    breadcrumb: str


def extract_candidates(
    headings: list[str], *, min_length: int = 4, max_titles: int = 60
) -> list[Candidate]:
    """
    Retient les titres de section qui désignent réellement une notion.

    Le fil d'Ariane « Algèbre de Boole > Introduction » est réduit à son
    dernier segment significatif — c'est lui qui nomme le contenu — mais le
    chemin complet est conservé pour deviner la matière.
    """
    seen: dict[str, Candidate] = {}
    for heading in headings:
        segments = [s.strip() for s in heading.split(">") if s.strip()]
        if not segments:
            continue

        # Dernier segment porteur de sens, sinon on remonte la hiérarchie.
        title = ""
        for segment in reversed(segments):
            if len(segment) >= min_length and not _NOISE_RE.match(segment):
                title = segment
                break
        if not title:
            continue

        key = normalise(title)
        if not key or key in seen:
            continue
        seen[key] = Candidate(title=title, breadcrumb=heading)
        if len(seen) >= max_titles:
            break
    return list(seen.values())
