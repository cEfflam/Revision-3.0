"""
AI Router — quel modèle pour quelle tâche.

L'idée à retenir : **la plupart des tâches n'ont pas besoin d'un gros modèle.**
Générer 10 flashcards à partir d'un texte fourni est du reformatage. Analyser
une synthèse de Culture Générale et proposer un nouveau plan demande du
raisonnement. Payer le prix du second pour faire le premier, c'est brûler son
budget en trois semaines — pour un résultat souvent identique.

Trois paliers :

  CHEAP      Reformatage, extraction, génération de cartes, corrections
             courtes. Rapide et quasi gratuit. ~90 % des appels.
  STANDARD   Explications pédagogiques, conversation, cas pratiques.
  REASONING  Analyse de copie, correction argumentée, construction de roadmap,
             diagnostic de code complexe. Cher et lent : à réserver.

Chaque palier a une chaîne de repli. Si le modèle principal est indisponible
(rate limit, panne du fournisseur), on descend d'un cran plutôt que de rendre
une erreur à l'utilisateur.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.config import settings


class Tier(StrEnum):
    cheap = "cheap"
    standard = "standard"
    reasoning = "reasoning"


class AiTask(StrEnum):
    """Toutes les tâches IA de l'application, nommées explicitement."""

    # ── Génération de contenu à partir de documents ───────────────────────
    flashcards = "flashcards"
    quiz = "quiz"
    summary = "summary"
    mindmap = "mindmap"
    node_suggestions = "node_suggestions"

    # ── Moteurs par matière ──────────────────────────────────────────────
    chat = "chat"
    explain_code = "explain_code"
    sql_review = "sql_review"
    math_hint = "math_hint"
    cge_analysis = "cge_analysis"
    cejm_case = "cejm_case"
    english_chat = "english_chat"

    # ── Coaching ─────────────────────────────────────────────────────────
    journal = "journal"
    roadmap = "roadmap"
    error_analysis = "error_analysis"


# Le tableau de routage. C'est le seul endroit à modifier pour changer la
# politique de coût de toute l'application.
TASK_TIER: dict[AiTask, Tier] = {
    AiTask.flashcards: Tier.cheap,
    AiTask.quiz: Tier.cheap,
    AiTask.summary: Tier.cheap,
    AiTask.mindmap: Tier.cheap,
    AiTask.node_suggestions: Tier.cheap,
    AiTask.english_chat: Tier.cheap,
    AiTask.chat: Tier.standard,
    AiTask.explain_code: Tier.standard,
    AiTask.sql_review: Tier.standard,
    # Socratique : ne jamais lâcher la réponse tout en restant utile demande
    # une vraie retenue. Les petits modèles craquent et donnent la solution.
    AiTask.math_hint: Tier.standard,
    AiTask.cejm_case: Tier.standard,
    AiTask.journal: Tier.cheap,
    AiTask.cge_analysis: Tier.reasoning,
    AiTask.roadmap: Tier.reasoning,
    AiTask.error_analysis: Tier.reasoning,
}

# Températures par tâche : basse quand on veut de la rigueur, plus haute quand
# on veut de la variété (ne jamais générer deux fois le même exercice).
TASK_TEMPERATURE: dict[AiTask, float] = {
    AiTask.flashcards: 0.4,
    AiTask.quiz: 0.7,
    AiTask.summary: 0.2,
    AiTask.mindmap: 0.3,
    AiTask.node_suggestions: 0.2,
    AiTask.chat: 0.5,
    AiTask.explain_code: 0.3,
    AiTask.sql_review: 0.2,
    AiTask.math_hint: 0.4,
    AiTask.cge_analysis: 0.3,
    AiTask.cejm_case: 0.5,
    AiTask.english_chat: 0.7,
    AiTask.journal: 0.6,
    AiTask.roadmap: 0.3,
    AiTask.error_analysis: 0.2,
}

# Tâches dont la réponse doit être du JSON strict (parsée par le backend).
JSON_TASKS: frozenset[AiTask] = frozenset(
    {
        AiTask.flashcards,
        AiTask.quiz,
        AiTask.mindmap,
        AiTask.node_suggestions,
        AiTask.cge_analysis,
        AiTask.roadmap,
    }
)

# Plafond de génération par tâche. Ce n'est pas de la radinerie : sans borne,
# un modèle bavard peut tripler la facture d'une simple génération de cartes
# en délayant. Chaque valeur correspond à ce que la tâche exige réellement.
MAX_TOKENS: dict[AiTask, int] = {
    AiTask.summary: 700,
    AiTask.journal: 400,
    AiTask.math_hint: 600,
    AiTask.flashcards: 1600,
    AiTask.quiz: 1600,
    AiTask.node_suggestions: 1200,
    AiTask.chat: 1200,
    AiTask.english_chat: 800,
    AiTask.explain_code: 1600,
    AiTask.sql_review: 1400,
    AiTask.cejm_case: 1600,
    AiTask.cge_analysis: 2500,
    AiTask.roadmap: 2500,
    AiTask.error_analysis: 1500,
}
DEFAULT_MAX_TOKENS = 1200


def max_tokens_for(task: AiTask) -> int:
    return MAX_TOKENS.get(task, DEFAULT_MAX_TOKENS)


def reasoning_enabled(task: AiTask) -> bool:
    """
    Le raisonnement doit-il être activé pour cette tâche ?

    ⚠️ C'est LE poste de dépense à surveiller. Les jetons de raisonnement sont
    facturés comme les autres, et un modèle qui « réfléchit » peut en produire
    plusieurs milliers avant d'écrire un seul mot de réponse. Sur une tâche de
    reformatage (générer des flashcards à partir d'un texte fourni), ça n'est
    qu'une facture multipliée sans aucun gain de qualité.

    Règle : uniquement sur le palier `reasoning`, c'est-à-dire les trois tâches
    qui exigent réellement une analyse — audit de copie CGE, construction de
    roadmap, et recherche de motifs dans l'historique d'erreurs.
    """
    return tier_for(task) is Tier.reasoning


def tier_for(task: AiTask) -> Tier:
    return TASK_TIER.get(task, Tier.standard)


def temperature_for(task: AiTask) -> float:
    return TASK_TEMPERATURE.get(task, 0.5)


def expects_json(task: AiTask) -> bool:
    return task in JSON_TASKS


def model_chain(task: AiTask) -> list[str]:
    """
    Modèle principal puis replis, du plus adapté au plus sûr.

    On dédoublonne en préservant l'ordre : si deux paliers sont configurés sur
    le même slug, inutile de retenter le même modèle.
    """
    tier = tier_for(task)
    ladders: dict[Tier, list[str]] = {
        Tier.reasoning: [
            settings.AI_MODEL_REASONING,
            settings.AI_MODEL_STANDARD,
            settings.AI_MODEL_CHEAP,
        ],
        Tier.standard: [settings.AI_MODEL_STANDARD, settings.AI_MODEL_CHEAP],
        Tier.cheap: [settings.AI_MODEL_CHEAP, settings.AI_MODEL_STANDARD],
    }
    seen: set[str] = set()
    chain: list[str] = []
    for model in ladders[tier]:
        if model and model not in seen:
            seen.add(model)
            chain.append(model)
    return chain
