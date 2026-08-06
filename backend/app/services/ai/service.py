"""
Fonctions IA de haut niveau — c'est ce que les endpoints appellent.

Chaînage type : contexte (RAG) → prompt système (pédagogie) → modèle (routeur)
→ parsing → objets Python typés. Les endpoints ne manipulent jamais de prompt
ni de JSON brut.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CardKind, Subject
from app.models.user import User
from app.services.ai.openrouter import (
    ChatMessage,
    Completion,
    get_ai_client,
    parse_json_response,
)
from app.services.ai.exam_formats import format_for
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
async def learner_context(
    db: AsyncSession, user: User, *, subject: str | None = None, limit: int = 6
) -> str:
    """
    Décrit l'état d'avancement de l'étudiant, pour l'injecter dans le prompt.

    Sans ce bloc, l'IA répond dans le vide : elle ignore si la notion est
    acquise ou fraîche, si l'étudiant s'est déjà planté dessus, et à quel
    niveau parler. Deux étudiants posant la même question reçoivent alors la
    même réponse — ce qui est précisément ce qu'un tuteur ne fait pas.

    Volontairement compact (quelques centaines de caractères) : c'est du
    contexte envoyé à CHAQUE appel, il ne doit pas peser sur la facture.
    """
    from app.models.graph import KnowledgeNode

    stmt = select(KnowledgeNode).where(KnowledgeNode.user_id == user.id)
    if subject:
        stmt = stmt.where(KnowledgeNode.subject == subject)

    nodes = (
        await db.execute(
            stmt.where(KnowledgeNode.review_count > 0)
            .order_by(KnowledgeNode.mastery.asc())
            .limit(limit)
        )
    ).scalars().all()

    if not nodes:
        return ""

    fragile = [n for n in nodes if n.mastery < 0.6]
    solide = [n for n in nodes if n.mastery >= 0.85]

    lines = ["### Ce que je sais de l'étudiant"]
    if fragile:
        lines.append(
            "Notions fragiles : "
            + ", ".join(f"{n.title} ({n.mastery:.0%})" for n in fragile[:4])
        )
    if solide:
        lines.append(
            "Notions acquises : " + ", ".join(n.title for n in solide[:4])
        )
    lines.append(
        "Appuie-toi sur ce qui est acquis pour expliquer ce qui est fragile. "
        "N'explique pas ce qu'il maîtrise déjà."
    )
    return "\n".join(lines)


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

    blocks: list[str] = []
    if context:
        blocks.append(f"### Extraits de mes documents\n{context}")

    # L'état de l'apprenant est ajouté à chaque échange : c'est ce qui permet
    # à l'IA de calibrer son niveau d'explication au lieu de répondre pareil
    # à tout le monde.
    profile = await learner_context(db, user, subject=subject)
    if profile:
        blocks.append(profile)

    blocks.append(f"### Ma question\n{question}" if blocks else question)
    messages.append(ChatMessage(role="user", content="\n\n".join(blocks)))

    completion = await get_ai_client().complete(messages, task=task, subject=subject)
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


async def generate_quiz(
    text: str, *, count: int = 5, subject: str = Subject.other.value
) -> list[dict]:
    """
    Produit un quiz de vérification. Retourne des dictionnaires bruts validés
    a minima : l'endpoint se charge de les couler dans le schéma Pydantic.
    """
    if not text.strip():
        return []

    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.quiz)),
        ChatMessage(
            role="user",
            content=(
                f"Matière : {subject}\n"
                f"Génère {count} questions à partir de ce contenu.\n\n{text[:8000]}"
            ),
        ),
    ]
    completion = await get_ai_client().complete(messages, task=AiTask.quiz)

    try:
        payload = parse_json_response(completion.text)
    except ValueError as exc:
        logger.error("Réponse quiz non parsable : %s", exc)
        return []

    raw = payload.get("questions", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []

    questions: list[dict] = []
    for item in raw[:count]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        if not question:
            continue
        choices = [str(c) for c in (item.get("choices") or []) if str(c).strip()]
        answer_index = item.get("answer_index", -1)
        # Un index hors bornes rendrait la question incorrigible côté client :
        # on la bascule alors en question ouverte plutôt que de la jeter.
        if not isinstance(answer_index, int) or not (
            0 <= answer_index < len(choices)
        ):
            answer_index, choices = -1, []
        questions.append(
            {
                "question": question,
                "kind": "mcq" if choices else "open",
                "choices": choices,
                "answer_index": answer_index,
                "explanation": str(item.get("explanation", "")).strip(),
            }
        )
    return questions


async def generate_roadmap(
    *,
    objective: str,
    target_date: str | None,
    daily_minutes: int,
    levels: dict[str, int],
    weak_nodes: list[str],
    max_steps: int = 12,
) -> dict:
    """
    Construit un parcours ordonné vers un objectif.

    On envoie le niveau déclaré ET les notions fragiles réellement mesurées :
    sans ces données, le modèle produit un plan de cours générique, exactement
    ce qu'on trouve déjà gratuitement sur internet.
    """
    context = [
        f"Objectif : {objective}",
        f"Date cible : {target_date or 'non fixée'}",
        f"Temps disponible : {daily_minutes} minutes par jour",
        f"Nombre d'étapes maximum : {max_steps}",
        "Niveau déclaré par matière : "
        + (", ".join(f"{k} {v}%" for k, v in levels.items()) or "non renseigné"),
        "Notions actuellement fragiles : "
        + (", ".join(weak_nodes) if weak_nodes else "aucune mesurée"),
    ]
    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.roadmap)),
        ChatMessage(role="user", content="\n".join(context)),
    ]
    completion = await get_ai_client().complete(messages, task=AiTask.roadmap)

    try:
        payload = parse_json_response(completion.text)
    except ValueError as exc:
        logger.error("Roadmap non parsable : %s", exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    payload["_model"] = completion.model
    payload["_mocked"] = completion.mocked
    return payload


async def generate_exam(
    user: User,
    *,
    subject: str,
    topic: str = "",
    node_titles: list[str] | None = None,
) -> dict:
    """
    Construit un sujet d'entraînement dans le style des annales de l'étudiant.

    DEUX RECHERCHES SÉPARÉES, et c'est tout l'intérêt :
      • dans la collection `exam` (ses BTS blancs) → le STYLE : façon de poser
        les questions, barème, type de contexte présenté ;
      • dans la collection `course` (ses cours) → le FOND : les notions.

    Une seule recherche mélangée donnerait un sujet au hasard entre les deux.
    Là, l'IA imite la forme de SES épreuves en interrogeant SON programme.
    """
    fmt = format_for(subject)
    query = topic or ", ".join(node_titles or []) or fmt.label

    exam_hits = await pipeline.search(
        user, query, collections=["exam"], subject=subject, top_k=4
    )
    course_hits = await pipeline.search(
        user, query, collections=["course", "note"], subject=subject, top_k=6
    )

    annales = pipeline.build_context(exam_hits, max_chars=4000)
    cours = pipeline.build_context(course_hits, max_chars=5000)

    blocks = [
        f"MATIÈRE : {subject}",
        f"TYPE D'ÉPREUVE : {fmt.label}",
        f"MÉTHODE ATTENDUE : {fmt.method}",
        f"DURÉE : {fmt.duration_minutes} minutes — BARÈME : {fmt.total_points} points",
    ]
    if topic:
        blocks.append(f"THÈME IMPOSÉ : {topic}")
    if node_titles:
        blocks.append("NOTIONS À COUVRIR : " + ", ".join(node_titles))

    blocks.append(
        "### ANNALES (modèle de FORME — ne recopie aucune question)\n"
        + (annales or "Aucune annale disponible : appuie-toi sur la méthode officielle.")
    )
    blocks.append("### COURS (le FOND à interroger)\n" + (cours or "Aucun cours importé."))

    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.exam_generate)),
        ChatMessage(role="user", content="\n\n".join(blocks)),
    ]
    completion = await get_ai_client().complete(
        messages, task=AiTask.exam_generate, subject=subject
    )

    try:
        payload = parse_json_response(completion.text)
    except ValueError as exc:
        logger.error(
            "Sujet d'examen non parsable : %s | début de la réponse : %s",
            exc,
            completion.text[:300],
        )
        return {}
    if not isinstance(payload, dict) or not payload.get("questions"):
        # Trace le contenu réel : sans elle, un modèle qui renvoie une
        # structure inattendue produit une erreur muette côté utilisateur.
        logger.warning(
            "Sujet sans questions exploitables | clés=%s | réponse=%s",
            list(payload.keys()) if isinstance(payload, dict) else type(payload),
            completion.text[:400],
        )
        return {}

    payload["_model"] = completion.model
    payload["_mocked"] = completion.mocked
    payload["_has_annales"] = bool(exam_hits)
    payload["_sources"] = _sources_from_hits(exam_hits + course_hits)
    return payload


async def evaluate_exam(
    *, subject: str, exercise: dict, answer: str
) -> dict:
    """Corrige une copie avec la grille de critères de l'épreuve."""
    fmt = format_for(subject)

    questions = "\n".join(
        f"{q.get('number', i + 1)}. ({q.get('points', '?')} pts) {q.get('text', '')}"
        for i, q in enumerate(exercise.get("questions") or [])
    )
    prompt = (
        f"MATIÈRE : {subject}\n"
        f"TYPE D'ÉPREUVE : {fmt.label}\n"
        f"BARÈME TOTAL : {exercise.get('total_points', fmt.total_points)} points\n"
        f"CRITÈRES D'ÉVALUATION :\n"
        + "\n".join(f"- {c}" for c in fmt.criteria)
        + f"\n\n### SUJET\n{exercise.get('title', '')}\n"
        f"{exercise.get('instructions', '')}\n\n"
        f"{exercise.get('context', '')}\n\n### QUESTIONS\n{questions}\n\n"
        f"### COPIE DE L'ÉTUDIANT\n{answer[:14000]}"
    )

    messages = [
        ChatMessage(role="system", content=system_prompt(AiTask.exam_evaluate)),
        ChatMessage(role="user", content=prompt),
    ]
    completion = await get_ai_client().complete(
        messages, task=AiTask.exam_evaluate, subject=subject
    )

    try:
        payload = parse_json_response(completion.text)
    except ValueError as exc:
        logger.error("Correction non parsable : %s", exc)
        return {}
    if not isinstance(payload, dict):
        return {}

    payload["_model"] = completion.model
    payload["_mocked"] = completion.mocked
    return payload


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
