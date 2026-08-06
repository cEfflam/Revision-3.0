"""
Client OpenRouter + mode simulé.

MODE SIMULÉ (AI_MOCK=true, valeur par défaut)
──────────────────────────────────────────────
Aucune requête réseau, aucune clé API, aucun coût : le client fabrique des
réponses plausibles et déterministes. Ça n'est pas un gadget — c'est ce qui
permet de développer et tester toute la chaîne (endpoints, parsing, affichage,
schéma de base) sans dépendre d'un fournisseur externe.

Passe `AI_MOCK=false` et renseigne `OPENROUTER_API_KEY` le jour où tu veux les
vrais modèles. Aucune autre ligne à changer.

REPLI (fallback)
────────────────
Un modèle peut être saturé, déprécié ou momentanément en panne. On parcourt la
chaîne fournie par l'AI Router jusqu'à obtenir une réponse, en journalisant
chaque échec. L'utilisateur ne voit une erreur que si tous les modèles ont
échoué.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx

from app.core.config import settings
from app.services.ai.router import (
    AiTask,
    estimate_cost,
    expects_json,
    max_tokens_for,
    model_chain,
    reasoning_enabled,
    required_json_key,
    role_for,
    temperature_for,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class Completion:
    text: str
    model: str
    tier: str
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # Jetons de « réflexion » produits avant la réponse. Facturés comme les
    # autres, et invisibles dans le texte renvoyé : on les compte à part pour
    # pouvoir repérer une tâche qui coûte cher sans raison.
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    mocked: bool = False
    attempts: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class AiUnavailable(RuntimeError):
    """Tous les modèles de la chaîne ont échoué."""


class OpenRouterClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.OPENROUTER_BASE_URL,
                timeout=httpx.Timeout(settings.AI_REQUEST_TIMEOUT),
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY or ''}",
                    # Ces deux en-têtes sont propres à OpenRouter : ils
                    # identifient l'application dans leurs statistiques et
                    # donnent parfois accès à des quotas plus larges.
                    "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                    "X-Title": settings.OPENROUTER_APP_NAME,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    @property
    def is_mocked(self) -> bool:
        return settings.AI_MOCK or not settings.OPENROUTER_API_KEY

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        task: AiTask,
        subject: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Completion:
        # `subject` permet à la matière d'imposer le modèle : générer un cas
        # pratique de CEJM est de la rédaction juridique (Qwen), générer un
        # exercice de SQL est de la logique (DeepSeek). Même tâche, deux
        # besoins opposés.
        chain = model_chain(task, subject)
        tier = role_for(task, subject).value

        if self.is_mocked:
            if not settings.AI_MOCK:
                logger.warning(
                    "OPENROUTER_API_KEY absente → réponse simulée pour la tâche %s.",
                    task.value,
                )
            return _mock_completion(task, messages, tier=tier)

        temp = temperature if temperature is not None else temperature_for(task)
        payload_base: dict[str, Any] = {
            "messages": [m.as_dict() for m in messages],
            "temperature": temp,
            "max_tokens": max_tokens or max_tokens_for(task),
            # Désactivé explicitement sur les tâches simples : c'est le premier
            # levier d'économie. Un modèle qui « réfléchit » facture ses jetons
            # de réflexion, même pour reformater un texte déjà fourni.
            "reasoning": {"enabled": reasoning_enabled(task, subject)},
        }
        if expects_json(task):
            # Tous les modèles n'honorent pas ce paramètre ; le parseur en aval
            # sait de toute façon récupérer du JSON entouré de texte.
            payload_base["response_format"] = {"type": "json_object"}

        wants_json = expects_json(task)
        required_key = required_json_key(task)
        attempts: list[str] = []

        # Chaque modèle a droit à deux essais sur une tâche JSON. Les modèles
        # renvoient parfois une structure incomplète ou du texte autour : c'est
        # non déterministe et observé en production. Un second essai coûte
        # quelques centièmes de centime ; une erreur affichée à l'utilisateur
        # coûte sa confiance.
        for model, attempt in ((m, a) for m in chain for a in range(2 if wants_json else 1)):
            started = time.perf_counter()
            try:
                payload = {**payload_base, "model": model}
                if attempt:
                    payload["messages"] = [
                        *payload_base["messages"],
                        {
                            "role": "system",
                            "content": (
                                "Ta réponse précédente n'était pas un JSON valide "
                                "et complet. Renvoie UNIQUEMENT l'objet JSON "
                                "demandé, tous champs remplis, sans aucun texte "
                                "avant ni après."
                            ),
                        },
                    ]
                response = await self._http().post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()

                choice = data["choices"][0]["message"]["content"] or ""

                if wants_json and not _is_usable_json(choice, required_key):
                    attempts.append(f"{model}#{attempt + 1}: JSON incomplet")
                    logger.warning(
                        "Réponse JSON inexploitable de %s (essai %s, clé « %s » "
                        "absente ou vide) — nouvel essai. Reçu : %r",
                        model,
                        attempt + 1,
                        required_key,
                        choice[:300],
                    )
                    continue

                usage = data.get("usage") or {}
                details = usage.get("completion_tokens_details") or {}
                prompt_details = usage.get("prompt_tokens_details") or {}

                completion = Completion(
                    text=choice.strip(),
                    model=model,
                    tier=tier,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                    reasoning_tokens=int(details.get("reasoning_tokens", 0) or 0),
                    cached_tokens=int(prompt_details.get("cached_tokens", 0) or 0),
                    attempts=attempts,
                )
                _log_usage(task, completion, subject)
                return completion
            except Exception as exc:
                attempts.append(f"{model}: {type(exc).__name__}")
                logger.warning("Modèle %s indisponible (%s) — repli.", model, exc)

        if wants_json:
            raise AiUnavailable(
                "Aucun modèle n'a produit un JSON exploitable. Tentatives : "
                + " | ".join(attempts)
            )

        raise AiUnavailable(
            "Aucun modèle n'a répondu. Tentatives : " + " | ".join(attempts)
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


@lru_cache(maxsize=1)
def get_ai_client() -> OpenRouterClient:
    return OpenRouterClient()


def _log_usage(
    task: AiTask, completion: Completion, subject: str | None = None
) -> None:
    """
    Trace la consommation de chaque appel.

    Sans cette ligne, « l'IA coûte cher » reste une impression. Avec elle, on
    voit quelle tâche brûle quoi, et on sait laquelle optimiser en premier.
    Repérable dans les logs : `docker compose logs backend | grep "coût"`.
    """
    cost = estimate_cost(
        task, completion.prompt_tokens, completion.completion_tokens, subject
    )
    logger.info(
        "coût | %-18s | %-30s | entrée %5d (%4d en cache) | sortie %5d "
        "(%4d de réflexion) | %8.6f $ | %4d ms",
        task.value,
        completion.model,
        completion.prompt_tokens,
        completion.cached_tokens,
        completion.completion_tokens,
        completion.reasoning_tokens,
        cost,
        completion.latency_ms,
    )


# ═════════════════════════════════════════════════════════════════════════
#  Extraction du JSON
# ═════════════════════════════════════════════════════════════════════════
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", flags=re.DOTALL)

def _is_usable_json(text: str, required_key: str | None) -> bool:
    """
    Le JSON est-il parsable ET porteur du contenu attendu ?

    Vérifier la seule syntaxe ne suffit pas : un objet qui contient le titre et
    l'énoncé mais pas la clé `questions` est parfaitement valide et totalement
    inutilisable. La clé exigée est déclarée par tâche dans le routeur.
    """
    try:
        payload = parse_json_response(text)
    except ValueError:
        return False
    if isinstance(payload, list):
        return bool(payload)
    if not isinstance(payload, dict):
        return False
    if required_key is None:
        return True
    return bool(payload.get(required_key))


def parse_json_response(text: str) -> Any:
    """
    Récupère un objet JSON dans une réponse de modèle.

    Les modèles ajoutent volontiers « Voici le JSON demandé : » puis un bloc
    ```json. On essaie donc, dans l'ordre : le texte tel quel, le contenu d'un
    bloc de code, puis la première accolade/crochet équilibré. Sans ça, un
    préambule bavard casse la fonctionnalité — et ça arrive tout le temps.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Réponse IA vide.")

    candidates: list[str] = [text]

    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    for opening, closing in (("{", "}"), ("[", "]")):
        start = text.find(opening)
        end = text.rfind(closing)
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Impossible d'extraire du JSON de : {text[:200]}…")


# ═════════════════════════════════════════════════════════════════════════
#  Réponses simulées
# ═════════════════════════════════════════════════════════════════════════
def _mock_completion(
    task: AiTask, messages: list[ChatMessage], *, tier: str
) -> Completion:
    text = _MOCK_BUILDERS.get(task, _mock_generic)(
        _mock_source(messages[-1].content if messages else "")
    )
    return Completion(
        text=text,
        model="mock",
        tier=tier,
        latency_ms=5,
        mocked=True,
    )


def _mock_source(content: str) -> str:
    """
    Isole le contenu réel des consignes qui le précèdent.

    Les messages utilisateur suivent tous le même gabarit :

        Matière : sql
        Génère 5 questions à partir de ce contenu.

        <le vrai contenu>

    Sans ce découpage, le mode simulé fabrique des questions à partir de la
    consigne elle-même — « À propos de "Génère 5 questions…" » — et la
    fonctionnalité paraît cassée alors qu'elle marche.

    Pas de repli sur le message complet si le contenu est court : mieux vaut
    un mock pauvre qu'un mock trompeur.
    """
    _, separator, body = content.partition("\n\n")
    return (body if separator else content).strip()


def _sentences(text: str, limit: int = 8) -> list[str]:
    parts = [
        s.strip(" -•\t")
        for s in re.split(r"(?<=[.!?])\s+|\n+", text)
        if len(s.strip()) > 25
    ]
    return parts[:limit] or ["Notion extraite du document importé"]


def _mock_flashcards(source: str) -> str:
    cards = [
        {
            "front": f"Quelle est l'idée clé de : « {s[:70]}… » ?",
            "back": s[:280],
            "kind": "basic",
            "hint": "Reformule avec tes propres mots avant de retourner la carte.",
            "explanation": "Carte simulée (AI_MOCK=true).",
        }
        for s in _sentences(source, 5)
    ]
    return json.dumps({"cards": cards}, ensure_ascii=False)


def _mock_quiz(source: str) -> str:
    questions = [
        {
            "question": f"À propos de « {s[:60]}… », quelle affirmation est exacte ?",
            "kind": "mcq",
            "choices": [s[:90], "Proposition erronée A", "Proposition erronée B"],
            "answer_index": 0,
            "explanation": "Question simulée (AI_MOCK=true).",
        }
        for s in _sentences(source, 3)
    ]
    return json.dumps({"questions": questions}, ensure_ascii=False)


def _mock_summary(source: str) -> str:
    points = _sentences(source, 3)
    body = "\n".join(f"- {p[:160]}" for p in points)
    return f"**Résumé exécutif (simulé)**\n\n{body}"


def _mock_mindmap(source: str) -> str:
    branches = [
        {"title": s[:50], "children": []} for s in _sentences(source, 4)
    ]
    return json.dumps(
        {"root": "Document importé", "branches": branches}, ensure_ascii=False
    )


def _mock_nodes(source: str) -> str:
    nodes = [
        {
            "slug": re.sub(r"[^a-z0-9]+", "-", s[:40].lower()).strip("-") or "notion",
            "title": s[:60],
            "kind": "concept",
            "subject": "other",
            "prerequisites": [],
        }
        for s in _sentences(source, 4)
    ]
    return json.dumps({"nodes": nodes}, ensure_ascii=False)


def _mock_cge(source: str) -> str:
    # Les `quote` sont des extraits RÉELS du texte soumis, pas du texte
    # inventé : sans ça, le mode simulé n'exercerait jamais le surlignage
    # côté interface, et on ne découvrirait le bug qu'avec une vraie clé API.
    excerpts = _sentences(source, 3)
    first = excerpts[0] if excerpts else ""
    second = excerpts[1] if len(excerpts) > 1 else first

    return json.dumps(
        {
            "score": 12,
            "issues": [
                {
                    "type": "repetition",
                    "severity": "warning",
                    "label": "Répétition d'idée",
                    "quote": second,
                    "detail": "Cette idée a déjà été formulée plus haut (simulé).",
                    "suggestion": "Fusionne les deux passages et garde la formulation la plus précise.",
                },
                {
                    "type": "transition",
                    "severity": "info",
                    "label": "Transition absente",
                    "quote": first,
                    "detail": "Le passage d'une partie à l'autre est abrupt (simulé).",
                    "suggestion": "Introduis un connecteur logique : « Dès lors », « À l'inverse ».",
                },
                {
                    "type": "plan",
                    "severity": "critical",
                    "label": "Plan perfectible",
                    "quote": "",  # problème global : ne cible aucun passage
                    "detail": "Les deux premières parties se recouvrent (simulé).",
                    "suggestion": "Distingue clairement constat et analyse.",
                },
            ],
            "strengths": ["Introduction claire", "Vocabulaire correct"],
            "next_step": "Retravaille les transitions entre les parties.",
        },
        ensure_ascii=False,
    )


def _mock_math(source: str) -> str:
    return (
        "Ne cherchons pas la réponse tout de suite.\n\n"
        "**Question 1.** Quelles données de l'énoncé sont réellement utiles ici ?\n"
        "**Question 2.** Reconnais-tu une forme déjà rencontrée ?\n"
        "**Question 3.** Que se passe-t-il si tu testes un cas simple ?\n\n"
        "_(guidage simulé — AI_MOCK=true)_"
    )


def _mock_roadmap(source: str) -> str:
    return json.dumps(
        {
            "objective": "Objectif simulé",
            "total_estimated_hours": 40,
            "steps": [
                {
                    "order": 1,
                    "title": "Consolider les bases SQL",
                    "subject": "sql",
                    "estimated_minutes": 240,
                    "prerequisites": [],
                    "why": "Prérequis de toutes les notions ORM.",
                },
                {
                    "order": 2,
                    "title": "Relations et jointures",
                    "subject": "sql",
                    "estimated_minutes": 180,
                    "prerequisites": ["Consolider les bases SQL"],
                    "why": "Bloque la compréhension de Doctrine.",
                },
            ],
        },
        ensure_ascii=False,
    )


def _mock_journal(source: str) -> str:
    return (
        "**Ta journée (simulé)**\n\n"
        "- Tu as consolidé 2 notions et corrigé 1 erreur récurrente.\n"
        "- Point fort : régularité maintenue.\n"
        "- Demain : reprends les jointures externes, encore fragiles."
    )


def _mock_generic(source: str) -> str:
    preview = source.strip().replace("\n", " ")[:200]
    return (
        "Réponse simulée (`AI_MOCK=true`). Le pipeline fonctionne : prompt reçu, "
        "routage effectué, réponse renvoyée.\n\n"
        f"> Début du prompt : « {preview}… »\n\n"
        "Mets `AI_MOCK=false` et une clé OpenRouter pour de vraies réponses."
    )


_MOCK_BUILDERS = {
    AiTask.flashcards: _mock_flashcards,
    AiTask.quiz: _mock_quiz,
    AiTask.summary: _mock_summary,
    AiTask.mindmap: _mock_mindmap,
    AiTask.node_suggestions: _mock_nodes,
    AiTask.cge_analysis: _mock_cge,
    AiTask.math_hint: _mock_math,
    AiTask.roadmap: _mock_roadmap,
    AiTask.journal: _mock_journal,
}
