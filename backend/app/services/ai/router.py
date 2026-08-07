"""
AI Router — quel modèle, avec quel budget, pour quelle tâche.

═══════════════════════════════════════════════════════════════════════════
DEUX RÔLES, PAS TROIS PALIERS
═══════════════════════════════════════════════════════════════════════════
Un « palier de puissance » abstrait ne veut rien dire. Ce qui compte, c'est
la NATURE de la tâche :

  LANGUAGE   Manipuler du texte : rédiger en français, structurer un cas de
             droit, produire du JSON propre, reformuler un cours en cartes.
             → Qwen 3.7 Flash. Excellent en français, très bon marché, et
               fiable sur le JSON structuré.

  REASONING  Enchaîner des étapes logiques sans se tromper : résoudre un
             exercice de maths, dérouler un algorithme, trouver la cause
             d'un bug, ordonner un parcours d'apprentissage.
             → DeepSeek V4 Flash avec le raisonnement activé. Il pose ses
               étapes avant de conclure, ce qui élimine les erreurs de
               logique en cours de route.

═══════════════════════════════════════════════════════════════════════════
LE RAISONNEMENT EST LE POSTE DE DÉPENSE N°1
═══════════════════════════════════════════════════════════════════════════
Les jetons de réflexion sont facturés au prix des jetons de sortie, et un
modèle peut en produire plusieurs milliers avant d'écrire un seul mot. Sur
une tâche de reformatage — générer des cartes à partir d'un texte déjà
fourni — c'est la facture multipliée pour zéro gain.

D'où la règle : le raisonnement n'est activé QUE sur les tâches du rôle
`reasoning`, jamais ailleurs. Voir docs/COUTS.md pour le chiffrage.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.config import settings


class ModelRole(StrEnum):
    language = "language"
    reasoning = "reasoning"


class AiTask(StrEnum):
    """Toutes les tâches IA de l'application, nommées explicitement."""

    # ── Génération de contenu à partir de documents ───────────────────────
    flashcards = "flashcards"
    quiz = "quiz"
    summary = "summary"
    mindmap = "mindmap"
    node_suggestions = "node_suggestions"
    node_synthesis = "node_synthesis"
    synthesis_review = "synthesis_review"
    feynman = "feynman"
    sql_sandbox = "sql_sandbox"
    pseudocode_review = "pseudocode_review"

    # ── Moteurs par matière ──────────────────────────────────────────────
    chat = "chat"
    explain_code = "explain_code"
    sql_review = "sql_review"
    math_hint = "math_hint"
    cge_analysis = "cge_analysis"
    cejm_case = "cejm_case"
    english_chat = "english_chat"

    # ── Entraînement type examen ─────────────────────────────────────────
    exam_generate = "exam_generate"
    exam_evaluate = "exam_evaluate"

    # ── Coaching ─────────────────────────────────────────────────────────
    journal = "journal"
    roadmap = "roadmap"
    error_analysis = "error_analysis"


# ═════════════════════════════════════════════════════════════════════════
#  Le tableau de routage — seul endroit à modifier pour changer la politique
# ═════════════════════════════════════════════════════════════════════════
TASK_ROLE: dict[AiTask, ModelRole] = {
    # ── Langue, rédaction, JSON structuré → Qwen ─────────────────────────
    AiTask.flashcards: ModelRole.language,       # JSON de création de cartes
    AiTask.quiz: ModelRole.language,
    AiTask.summary: ModelRole.language,
    AiTask.mindmap: ModelRole.language,
    AiTask.node_suggestions: ModelRole.language,
    # La matière décide en réalité (voir role_for) : synthétiser un cours de
    # droit est de la rédaction, synthétiser un cours de maths demande de ne
    # pas déformer une formule.
    AiTask.node_synthesis: ModelRole.language,
    # Relecture critique : c'est un travail de vérification, pas de rédaction.
    # Affirmer qu'un cours de professeur est faux demande du raisonnement.
    AiTask.synthesis_review: ModelRole.reasoning,
    # Feynman : repérer une lacune dans une explication demande de comparer
    # deux formulations, pas de rédiger.
    AiTask.feynman: ModelRole.reasoning,
    # Le SQL généré doit s'exécuter réellement : aucune approximation permise.
    AiTask.sql_sandbox: ModelRole.reasoning,
    AiTask.pseudocode_review: ModelRole.reasoning,
    AiTask.chat: ModelRole.language,
    AiTask.english_chat: ModelRole.language,
    AiTask.journal: ModelRole.language,
    AiTask.cejm_case: ModelRole.language,        # droit : rédaction structurée
    AiTask.cge_analysis: ModelRole.language,     # français : finesse littéraire
    # ── Logique, calcul, code → DeepSeek avec raisonnement ───────────────
    AiTask.math_hint: ModelRole.reasoning,
    AiTask.explain_code: ModelRole.reasoning,
    AiTask.sql_review: ModelRole.reasoning,
    AiTask.roadmap: ModelRole.reasoning,         # ordonnancement de prérequis
    AiTask.error_analysis: ModelRole.reasoning,  # recherche de motifs
    # Les épreuves basculent selon la matière (voir role_for_subject) : par
    # défaut on prend le rôle prudent, car un sujet incohérent ou une note
    # fausse se voient immédiatement.
    AiTask.exam_generate: ModelRole.reasoning,
    AiTask.exam_evaluate: ModelRole.reasoning,
}

# Quel modèle pour quelle MATIÈRE, quand la tâche seule ne suffit pas à
# trancher. Concevoir un cas pratique de CEJM est un exercice de rédaction
# juridique ; concevoir un exercice de SQL demande de la logique. Même tâche,
# deux besoins opposés.
SUBJECT_ROLE: dict[str, ModelRole] = {
    "cejm": ModelRole.language,
    "cge": ModelRole.language,
    "english": ModelRole.language,
    "sql": ModelRole.reasoning,
    "dev": ModelRole.reasoning,
    "math": ModelRole.reasoning,
    "network": ModelRole.reasoning,
    "security": ModelRole.reasoning,
    "cloud": ModelRole.reasoning,
    "devops": ModelRole.reasoning,
}


def role_for_subject(subject: str | None) -> ModelRole | None:
    """Rôle imposé par la matière, ou None pour laisser décider la tâche."""
    return SUBJECT_ROLE.get(subject or "")

# Températures : basse quand on veut de la rigueur, plus haute quand on veut
# de la variété (ne jamais générer deux fois le même exercice).
TASK_TEMPERATURE: dict[AiTask, float] = {
    AiTask.flashcards: 0.4,
    AiTask.quiz: 0.7,
    AiTask.summary: 0.2,
    AiTask.mindmap: 0.3,
    AiTask.node_suggestions: 0.2,
    # Très basse : une synthèse doit restituer, pas inventer.
    AiTask.node_synthesis: 0.15,
    AiTask.synthesis_review: 0.2,
    AiTask.feynman: 0.2,
    # Assez haute pour varier les exercices, assez basse pour que le SQL
    # généré reste syntaxiquement irréprochable.
    AiTask.sql_sandbox: 0.6,
    AiTask.pseudocode_review: 0.1,
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
    # Assez haute pour que deux entraînements ne donnent jamais le même sujet,
    # mais pas davantage : au-delà de 0.6, le modèle devient créatif sur la
    # STRUCTURE aussi et omet régulièrement la clé « questions ».
    AiTask.exam_generate: 0.6,
    # Basse : une note doit être reproductible, pas créative.
    AiTask.exam_evaluate: 0.1,
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
        AiTask.exam_generate,
        AiTask.exam_evaluate,
        AiTask.synthesis_review,
        AiTask.feynman,
        AiTask.sql_sandbox,
        AiTask.pseudocode_review,
    }
)

# Plafond de génération par tâche. Ce n'est pas de la radinerie : sans borne,
# un modèle bavard délaye et triple la facture pour le même contenu utile.
#
# Ordre de grandeur : 1 jeton ≈ 0,75 mot en français. 400 jetons ≈ 300 mots,
# soit largement de quoi écrire un bilan de 5 lignes.
#
# Les tâches de raisonnement ont un plafond plus large : les jetons de
# réflexion s'imputent sur le même budget, et une borne trop basse tronquerait
# la réponse APRÈS que le modèle a déjà payé sa réflexion — le pire des cas.
MAX_TOKENS: dict[AiTask, int] = {
    # Langue
    AiTask.journal: 500,
    AiTask.summary: 800,
    AiTask.english_chat: 900,
    AiTask.chat: 1400,
    AiTask.node_suggestions: 1400,
    # Le texte le plus long produit par l'application, et le plus rentable :
    # généré une fois, relu à chaque question sur la notion.
    AiTask.node_synthesis: 2500,
    AiTask.synthesis_review: 2000,
    AiTask.feynman: 2500,
    # Schéma + jeu de données + solution : le plus volumineux de tous.
    AiTask.sql_sandbox: 3500,
    # Large, et pour une raison mesurée : sur une tâche de raisonnement, la
    # réflexion consomme le MÊME budget que la réponse. Un premier essai à
    # 3000 a produit 2256 jetons de réflexion, ne laissant que 744 pour le
    # JSON — tronqué, donc inexploitable. La borne doit couvrir les deux.
    AiTask.pseudocode_review: 6000,
    AiTask.flashcards: 2000,
    AiTask.quiz: 2000,
    AiTask.cejm_case: 2000,
    AiTask.cge_analysis: 3000,
    # Raisonnement (réflexion incluse dans le budget)
    AiTask.math_hint: 2500,
    AiTask.sql_review: 3000,
    AiTask.explain_code: 3500,
    AiTask.error_analysis: 3000,
    AiTask.roadmap: 4000,
    # Un sujet d'examen complet (contexte + questions) est long par nature.
    AiTask.exam_generate: 4000,
    AiTask.exam_evaluate: 3500,
}
DEFAULT_MAX_TOKENS = 1500


def role_for(task: AiTask, subject: str | None = None) -> ModelRole:
    """
    Le rôle vient de la matière si elle en impose un, sinon de la tâche.

    L'ordre compte : « générer un sujet » n'a pas le même besoin en CEJM
    (rédaction juridique → Qwen) qu'en SQL (logique → DeepSeek).
    """
    if subject:
        override = role_for_subject(subject)
        if override is not None:
            return override
    return TASK_ROLE.get(task, ModelRole.language)


def temperature_for(task: AiTask) -> float:
    return TASK_TEMPERATURE.get(task, 0.5)


# Clé que la réponse DOIT contenir, non vide, pour être exploitable.
# Sans cette table, un modèle qui renvoie « title + context » sans la moindre
# question produit un JSON parfaitement valide et totalement inutile — et
# l'utilisateur voit une erreur sans comprendre pourquoi.
REQUIRED_JSON_KEY: dict[AiTask, str] = {
    AiTask.flashcards: "cards",
    AiTask.quiz: "questions",
    AiTask.node_suggestions: "nodes",
    AiTask.roadmap: "steps",
    AiTask.exam_generate: "questions",
    # Pas de clé exigée pour la relecture : une liste de remarques vide est un
    # résultat valide et même souhaitable — la synthèse est alors fiable.
}


def expects_json(task: AiTask) -> bool:
    return task in JSON_TASKS


def required_json_key(task: AiTask) -> str | None:
    return REQUIRED_JSON_KEY.get(task)


def max_tokens_for(task: AiTask) -> int:
    return MAX_TOKENS.get(task, DEFAULT_MAX_TOKENS)


def reasoning_enabled(task: AiTask, subject: str | None = None) -> bool:
    """
    Le raisonnement doit-il être activé ? Uniquement sur le rôle `reasoning`,
    et seulement si l'interrupteur global `AI_REASONING` est levé.
    """
    return settings.AI_REASONING and role_for(task, subject) is ModelRole.reasoning


def model_for(role: ModelRole) -> str:
    return (
        settings.AI_MODEL_REASONING
        if role is ModelRole.reasoning
        else settings.AI_MODEL_LANGUAGE
    )


def model_chain(task: AiTask, subject: str | None = None) -> list[str]:
    """
    Modèle principal, puis repli sur l'autre rôle.

    Le repli est volontairement croisé : si Qwen est saturé, DeepSeek prendra
    le relais sur une tâche de rédaction. Le résultat sera un peu plus cher et
    peut-être moins fin en français, mais l'utilisateur obtient une réponse au
    lieu d'une erreur.
    """
    role = role_for(task, subject)
    primary = model_for(role)
    secondary = model_for(
        ModelRole.language if role is ModelRole.reasoning else ModelRole.reasoning
    )
    chain = [m for m in (primary, secondary) if m]
    # Dédoublonne en préservant l'ordre (cas où les deux rôles pointent sur
    # le même slug).
    seen: set[str] = set()
    return [m for m in chain if not (m in seen or seen.add(m))]


# ═════════════════════════════════════════════════════════════════════════
#  Tarification — pour chiffrer chaque appel
# ═════════════════════════════════════════════════════════════════════════
def price_per_million(role: ModelRole) -> tuple[float, float]:
    """(prix entrée, prix sortie) en dollars par million de jetons."""
    if role is ModelRole.reasoning:
        return settings.AI_PRICE_REASONING_IN, settings.AI_PRICE_REASONING_OUT
    return settings.AI_PRICE_LANGUAGE_IN, settings.AI_PRICE_LANGUAGE_OUT


def estimate_cost(
    task: AiTask,
    prompt_tokens: int,
    completion_tokens: int,
    subject: str | None = None,
) -> float:
    """
    Coût en dollars d'un appel.

    Les jetons de réflexion sont déjà comptés dans `completion_tokens` par
    OpenRouter : ils sont facturés au tarif de sortie, pas à un tarif à part.
    """
    price_in, price_out = price_per_million(role_for(task, subject))
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000
