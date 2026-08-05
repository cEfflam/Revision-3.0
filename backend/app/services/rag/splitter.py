"""
Découpage du texte en *chunks* — l'étape la plus sous-estimée du RAG.

Pourquoi ça compte autant : la recherche vectorielle renvoie des chunks, et
c'est le chunk brut qui part dans le prompt de l'IA. Un mauvais découpage
produit des extraits amputés, l'IA répond à côté, et on accuse le modèle alors
que le problème vient d'ici.

Stratégie, du plus fort au plus faible signal :

  1. TITRES     On coupe d'abord aux titres Markdown. Une section de cours est
                une unité de sens ; la respecter suffit dans 80 % des cas.
  2. PARAGRAPHES Dans une section trop longue, on regroupe des paragraphes
                entiers jusqu'à la taille cible. Jamais au milieu d'un mot.
  3. PHRASES    Un paragraphe seul plus long que la limite (tableau, liste
                dense) est coupé aux fins de phrase.

CHEVAUCHEMENT : chaque chunk reprend la fin du précédent (~150 caractères).
Ça évite de perdre l'information qui tombe pile sur une frontière : la phrase
« ...pour cela, on utilise INNER JOIN » doit se retrouver dans les deux chunks,
sinon la réponse est introuvable.

Chaque chunk conserve son titre de section. Ce titre est réinjecté dans le
prompt : l'IA sait ainsi que l'extrait vient de « 3.2 Les jointures externes »
et peut citer sa source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", flags=re.MULTILINE)
SENTENCE_RE = re.compile(r"(?<=[.!?:;])\s+")


@dataclass(slots=True)
class TextChunk:
    ordinal: int
    content: str
    heading: str = ""

    @property
    def char_count(self) -> int:
        return len(self.content)


@dataclass(slots=True)
class _Section:
    heading: str
    body: str


def split_text(
    text: str,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 150,
    min_chars: int = 80,
) -> list[TextChunk]:
    """
    Découpe un texte Markdown en chunks prêts à vectoriser.

    `min_chars` élimine les fragments trop courts (un titre orphelin, une ligne
    de numérotation) : ils polluent l'index sans rien apporter.
    """
    text = (text or "").strip()
    if not text:
        return []

    overlap_chars = max(0, min(overlap_chars, max_chars // 3))
    chunks: list[str] = []
    headings: list[str] = []

    for section in _split_sections(text):
        for piece in _split_section_body(
            section.body, max_chars=max_chars, overlap_chars=overlap_chars
        ):
            chunks.append(piece)
            headings.append(section.heading)

    result: list[TextChunk] = []
    for content, heading in zip(chunks, headings, strict=True):
        cleaned = content.strip()
        # On garde un chunk court s'il est seul : mieux vaut un petit index
        # qu'un document invisible dans la recherche.
        if len(cleaned) < min_chars and len(chunks) > 1:
            continue
        result.append(
            TextChunk(ordinal=len(result), content=cleaned, heading=heading)
        )
    return result


def _split_sections(text: str) -> list[_Section]:
    """
    Découpe aux titres Markdown en conservant la hiérarchie.

    Le titre stocké est le chemin complet (« Chapitre 3 > Les jointures »),
    beaucoup plus informatif qu'un titre isolé quand il finit dans un prompt.
    """
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [_Section(heading="", body=text)]

    sections: list[_Section] = []

    # Texte avant le premier titre (préambule, page de garde).
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(_Section(heading="", body=preamble))

    # `path[i]` = titre courant au niveau i+1.
    path: list[str] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()

        path = path[: level - 1]
        while len(path) < level - 1:
            path.append("")
        path.append(title)

        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if not body:
            continue

        breadcrumb = " > ".join(p for p in path if p)
        sections.append(_Section(heading=breadcrumb, body=body))

    return sections


def _split_section_body(
    body: str, *, max_chars: int, overlap_chars: int
) -> list[str]:
    body = body.strip()
    if not body:
        return []
    if len(body) <= max_chars:
        return [body]

    units = _atomic_units(body, max_chars=max_chars)

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = _tail(current, overlap_chars)
            candidate = f"{tail}\n\n{unit}" if tail else unit
            # Le chevauchement ne doit JAMAIS faire déborder le chunk suivant :
            # `tail` + `unit` peut dépasser la limite alors que `unit` seul la
            # respecte. Dans ce cas on sacrifie le chevauchement — un chunk
            # trop gros serait tronqué à l'aveugle par le modèle d'embeddings,
            # ce qui coûte bien plus cher qu'une frontière sans recouvrement.
            current = candidate if len(candidate) <= max_chars else unit
        else:
            current = unit

    if current.strip():
        chunks.append(current)
    return chunks


def _atomic_units(body: str, *, max_chars: int) -> list[str]:
    """Paragraphes, éclatés en phrases si l'un dépasse à lui seul la limite."""
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue

        buffer = ""
        for sentence in SENTENCE_RE.split(paragraph):
            candidate = f"{buffer} {sentence}".strip()
            if len(candidate) <= max_chars:
                buffer = candidate
            else:
                if buffer:
                    units.append(buffer)
                # Phrase seule plus longue que la limite (rare : liste sans
                # ponctuation) → coupe franche, en dernier recours.
                buffer = sentence if len(sentence) <= max_chars else ""
                if not buffer:
                    units.extend(
                        sentence[i : i + max_chars]
                        for i in range(0, len(sentence), max_chars)
                    )
        if buffer:
            units.append(buffer)
    return units


def _tail(text: str, size: int) -> str:
    """Fin de chunk servant de chevauchement, coupée sur un mot entier."""
    if size <= 0 or len(text) <= size:
        return ""
    fragment = text[-size:]
    space = fragment.find(" ")
    return fragment[space + 1 :].strip() if space != -1 else fragment.strip()
