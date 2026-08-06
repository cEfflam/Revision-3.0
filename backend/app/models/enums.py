"""Vocabulaire métier de REVISIO — partagé par les modèles et les schémas."""

from __future__ import annotations

from enum import StrEnum


class NodeKind(StrEnum):
    """Granularité d'un nœud du graphe de connaissances."""

    domain = "domain"    # ex. « Développement »
    topic = "topic"      # ex. « SQL »
    skill = "skill"      # ex. « Jointures »
    concept = "concept"  # ex. « INNER JOIN »


class NodeStatus(StrEnum):
    locked = "locked"        # prérequis non validés → grisé dans le Skill Tree
    available = "available"  # débloqué, jamais travaillé
    learning = "learning"    # en cours d'acquisition
    mastered = "mastered"    # maîtrisé
    critical = "critical"    # régression détectée → priorité de révision


class EdgeRelation(StrEnum):
    """
    Sens de lecture d'une arête : source → target.
    `prerequisite` : il faut maîtriser `source` avant d'attaquer `target`.
    """

    prerequisite = "prerequisite"
    part_of = "part_of"
    related = "related"


class Subject(StrEnum):
    """Matières du BTS SIO + extensions futures."""

    dev = "dev"
    sql = "sql"
    network = "network"
    security = "security"
    math = "math"
    cejm = "cejm"
    cge = "cge"
    english = "english"
    cloud = "cloud"
    devops = "devops"
    other = "other"


# Libellés affichables des matières. Définis côté backend pour que l'API et
# l'interface ne divergent jamais : un libellé recopié dans le frontend finit
# toujours par se désynchroniser.
SUBJECT_LABELS: dict[str, str] = {
    Subject.dev.value: "Développement",
    Subject.sql.value: "SQL",
    Subject.network.value: "Réseau",
    Subject.security.value: "Cybersécurité",
    Subject.math.value: "Mathématiques",
    Subject.cejm.value: "CEJM",
    Subject.cge.value: "Culture générale",
    Subject.english.value: "Anglais",
    Subject.cloud.value: "Cloud",
    Subject.devops.value: "DevOps",
    Subject.other.value: "Autre",
}


class CardKind(StrEnum):
    basic = "basic"    # question / réponse
    cloze = "cloze"    # texte à trous
    code = "code"      # extrait de code à compléter ou corriger
    open = "open"      # réponse rédigée, évaluée par l'IA


class CardState(StrEnum):
    """États du cycle SRS."""

    new = "new"
    learning = "learning"
    review = "review"
    relearning = "relearning"


class Rating(StrEnum):
    """
    Auto-évaluation après une carte. Volontairement limité à 4 choix :
    au-delà, l'utilisateur hésite et la note perd sa valeur prédictive.
    """

    again = "again"  # oublié
    hard = "hard"    # retrouvé difficilement
    good = "good"    # retrouvé correctement
    easy = "easy"    # immédiat


class DocumentCollection(StrEnum):
    """Collections de la bibliothèque — pilote aussi le routage dans Qdrant."""

    course = "course"
    exam = "exam"    # BTS blancs, annales
    error = "error"  # historique de tes erreurs
    note = "note"


class DocumentStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class GoalKind(StrEnum):
    diploma = "diploma"
    certification = "certification"
    career = "career"
    language = "language"
    custom = "custom"


class LearningEngine(StrEnum):
    """Moteur pédagogique mobilisé pendant une session."""

    srs = "srs"
    dev = "dev"
    sql = "sql"
    network = "network"
    security = "security"
    math = "math"
    cejm = "cejm"
    cge = "cge"
    english = "english"
    chat = "chat"
