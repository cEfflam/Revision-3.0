"""
Fonctions IA de haut niveau — c'est ce que les endpoints appellent.

Chaînage type : contexte (RAG) → prompt système (pédagogie) → modèle (routeur)
→ parsing → objets Python typés. Les endpoints ne manipulent jamais de prompt
ni de JSON brut.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CardKind, Subject
from app.models.user import User
from app.services.ai.openrouter import (
    ChatMessage,
    Completion,
    get_ai_client,
    parse_json_response,
)
from app.services.ai.prompts import system_prompt
from app.services.ai.router import AiTask
from app.services.rag import pipeline
from app.services.rag.qdrant import SearchHit

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Source:
    index: int
    document_title: str
    heading: str
    excerpt: str
    score: float


@dataclass(slots=True)
class AnswerResult:
    answer: str
    sources: list[Source] = field(default_factory=list)
    model: str = ""
    mocked: bool = False
    latency_ms: int = 0
    tokens: int = 0


@dataclass(slots=True)
class CardDraft:
    front: str
    back: str
    kind: str = CardKind.basic.value
    hint: str = ""
    explanation: str = ""


def _sources_from_hits(hits: list[SearchHit]) -> list[Source]:
    return [
        Source(
            index=index,
            document_title=hit.document_title,
            heading=hit.heading,
            excerpt=hit.text[:400],
            score=round(hit.score, 4),
        )
        for index, hit in enumerate(hits, start=1)
    ]


def _result(completion: Completion, hits: list[SearchHit]) -> AnswerResult:
    return AnswerResult(
        answer=completion.text,
        sources=_sources_from_hits(hits),
        model=completion.model,
        mocked=completion.mocked,
        latency_ms=completion.latency_ms,
        tokens=completion.total_tokens,
    )


# ═════════════════════════════════════════════════════════════════════════
#  Question / réponse ancrée dans les documents (RAG)
# ═════════════════════════════════════════════════════════════════════════
async def ask(
    db: AsyncSession,
    user: User,
    question: str,
    *,
    task: AiTask = AiTask.chat,
    subject: str | None = None,
    collections: list[str] | None = None,
    use_rag: bool = True,
    history: list[ChatMessage] | None = None,
) -> AnswerResult:
    """
    Répond à une question en s'appuyant sur les documents de l'utilisateur.

    `use_rag=False` pour les moteurs qui n'ont pas besoin des cours (guidage
    mathématique, conversation en anglais) : chercher dans les documents
    coûterait une vectorisation pour rien.
    """
    hits: list[SearchHit] = []
    context = ""

    if use_rag:
        hits = await pipeline.search(
            user, question, collections=collections, subject=subject
        )
        context = pipeline.build_context(hits)

    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt(task))
    ]
    if history:
        messages.extend(history[-10:])  # fenêtre glissante : 5 échanges

    user_content = question
    if context:
        user_content = (
            "### Extraits de mes documents\n"
            f"{context}\n\n"
            "### Ma question\n"
            f"{question}"
        )
    messages.append(ChatMessage(role="user", content=user_content))

    completion = await get_ai_client().complete(messages, task=task)
    return _result(completion, hits)


# ═════════════════════════════════════════════════════════════════════════
#  Génération de contenu
# ═════════════════════════════════════════════════════════════════════════
async def generate_flashcards(
    text: str, *, count: int = 8, subject: str = Subject.other.value
) -> list[CardDraft]:
    """Transforme un texte de cours en flashcards prêtes à insérer."""
    if not text.strip():
        return []

    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.flashcards)),
        ChatMessage(
            role="user",
            content=(
                f"Matière : {subject}\n"
                f"Génère au maximum {count} flashcards à partir de ce contenu.\n\n"
                f"{text[:8000]}"
            ),
        ),
    ]
    completion = await get_ai_client().complete(messages, task=AiTask.flashcards)

    try:
        payload = parse_json_response(completion.text)
    except ValueError as exc:
        logger.error("Réponse flashcards non parsable : %s", exc)
        return []

    raw = payload.get("cards", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []

    valid_kinds = {k.value for k in CardKind}
    drafts: list[CardDraft] = []
    for item in raw[:count]:
        if not isinstance(item, dict):
            continue
        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        # Une carte sans question ou sans réponse est inutilisable : on la
        # jette plutôt que d'insérer du vide en base.
        if not front or not back:
            continue
        kind = str(item.get("kind", CardKind.basic.value)).strip()
        drafts.append(
            CardDraft(
                front=front,
                back=back,
                kind=kind if kind in valid_kinds else CardKind.basic.value,
                hint=str(item.get("hint", "")).strip(),
                explanation=str(item.get("explanation", "")).strip(),
            )
        )
    return drafts


async def generate_summary(text: str) -> str:
    if not text.strip():
        return ""
    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.summary)),
        ChatMessage(role="user", content=text[:12000]),
    ]
    # Pas de max_tokens ici : le plafond vient de router.MAX_TOKENS, seule
    # source de vérité. Le dupliquer dans chaque appel garantit qu'un jour
    # les deux divergeront.
    completion = await get_ai_client().complete(messages, task=AiTask.summary)
    return completion.text


async def suggest_nodes(text: str, *, subject: str = Subject.other.value) -> list[dict]:
    """Propose des nœuds de compétences et leurs prérequis pour le graphe."""
    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.node_suggestions)),
        ChatMessage(
            role="user",
            content=f"Matière dominante : {subject}\n\n{text[:8000]}",
        ),
    ]
    completion = await get_ai_client().complete(messages, task=AiTask.node_suggestions)
    try:
        payload = parse_json_response(completion.text)
    except ValueError:
        return []
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else payload
    return [n for n in nodes if isinstance(n, dict) and n.get("slug")]


async def analyse_writing(text: str) -> dict:
    """Audit d'un écrit de CGE — renvoie la structure JSON des problèmes."""
    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.cge_analysis)),
        ChatMessage(role="user", content=text[:12000]),
    ]
    completion = await get_ai_client().complete(messages, task=AiTask.cge_analysis)
    try:
        payload = parse_json_response(completion.text)
    except ValueError as exc:
        logger.error("Analyse CGE non parsable : %s", exc)
        return {
            "score": None,
            "issues": [],
            "strengths": [],
            "next_step": "L'analyse n'a pas pu être exploitée. Réessaie.",
        }
    return payload if isinstance(payload, dict) else {}


async def write_journal(stats: dict) -> str:
    """Résumé du soir à partir des statistiques de la journée."""
    lines = "\n".join(f"- {key} : {value}" for key, value in stats.items())
    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.journal)),
        ChatMessage(role="user", content=f"Données de la journée :\n{lines}"),
    ]
    completion = await get_ai_client().complete(messages, task=AiTask.journal)
    return completion.text
