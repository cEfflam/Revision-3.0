"""
Formats d'épreuve par matière.

C'est ici que le projet cesse d'être un Anki amélioré : un cas pratique de
CEJM ne se travaille pas comme une requête SQL, et une synthèse de Culture
Générale n'a rien à voir avec un exercice d'algorithmique. Chaque matière a
sa forme d'épreuve, sa méthode attendue, son barème et son format de réponse.

Ce tableau pilote trois choses :
  1. le PROMPT de génération — l'IA produit un sujet dans la bonne forme ;
  2. le PROMPT de correction — elle évalue avec les bons critères ;
  3. l'INTERFACE — le champ de réponse s'adapte (texte long, code, requête).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Subject


@dataclass(frozen=True, slots=True)
class ExamFormat:
    label: str
    #: Type de champ attendu côté interface : "text" | "code" | "sql"
    input_kind: str
    #: Méthode que l'étudiant doit appliquer — reprise telle quelle dans les
    #: consignes ET dans la grille de correction.
    method: str
    #: Critères d'évaluation, dans l'ordre de leur poids réel à l'examen.
    criteria: tuple[str, ...]
    duration_minutes: int
    total_points: int
    #: Aide affichée sous le champ de réponse.
    placeholder: str


EXAM_FORMATS: dict[str, ExamFormat] = {
    Subject.cejm.value: ExamFormat(
        label="Cas pratique juridique",
        input_kind="text",
        method=(
            "1. Les faits (uniquement ceux qui sont juridiquement pertinents) — "
            "2. Le problème de droit (une question fermée et précise) — "
            "3. La règle applicable (article, principe, jurisprudence, nommé) — "
            "4. L'application au cas d'espèce — "
            "5. La conclusion (réponse à la question posée en 2)"
        ),
        criteria=(
            "Qualification juridique des faits",
            "Formulation du problème de droit",
            "Exactitude de la règle citée",
            "Application au cas d'espèce (le cœur de la note)",
            "Clarté de la conclusion",
        ),
        duration_minutes=60,
        total_points=20,
        placeholder="Rédige en suivant les 5 étapes de la méthode juridique…",
    ),
    Subject.cge.value: ExamFormat(
        label="Synthèse / écriture personnelle",
        input_kind="text",
        method=(
            "Introduction annonçant la problématique et le plan — "
            "développement en parties équilibrées avec transitions explicites — "
            "conclusion qui répond sans introduire d'idée neuve. "
            "Pour une synthèse : confronter les documents, ne jamais donner "
            "son avis. Pour une écriture personnelle : thèse argumentée et "
            "illustrée par des références précises."
        ),
        criteria=(
            "Pertinence et équilibre du plan",
            "Confrontation des documents (synthèse) ou solidité de la thèse",
            "Qualité des transitions",
            "Richesse et précision du lexique",
            "Correction de la langue",
        ),
        duration_minutes=60,
        total_points=20,
        placeholder="Rédige ta synthèse ou ton écriture personnelle…",
    ),
    Subject.sql.value: ExamFormat(
        label="Requêtes SQL",
        input_kind="sql",
        method=(
            "Écrire une requête par question, formatée sur plusieurs lignes "
            "(SELECT / FROM / JOIN / WHERE / GROUP BY / ORDER BY alignés). "
            "Numéroter chaque réponse."
        ),
        criteria=(
            "Exactitude du résultat renvoyé",
            "Jointures correctes (pas de produit cartésien)",
            "Filtrage au bon endroit (WHERE avant agrégation, HAVING après)",
            "Lisibilité et formatage",
            "Efficacité de la requête",
        ),
        duration_minutes=45,
        total_points=20,
        placeholder="-- 1.\nSELECT ...\nFROM ...\nWHERE ...;",
    ),
    Subject.dev.value: ExamFormat(
        label="Exercice de développement",
        input_kind="code",
        method=(
            "Fournir le code demandé, commenté aux endroits non évidents. "
            "Respecter les conventions du langage et gérer les cas limites."
        ),
        criteria=(
            "Le code répond au besoin exprimé",
            "Gestion des cas limites et des erreurs",
            "Structure et lisibilité (nommage, découpage)",
            "Respect des conventions du langage",
            "Sécurité (injections, validation des entrées)",
        ),
        duration_minutes=60,
        total_points=20,
        placeholder="// Ton code ici",
    ),
    Subject.math.value: ExamFormat(
        label="Exercice de mathématiques",
        input_kind="text",
        method=(
            "Rédiger le raisonnement étape par étape. Justifier chaque passage. "
            "Encadrer ou souligner le résultat final."
        ),
        criteria=(
            "Justesse du résultat",
            "Rigueur du raisonnement",
            "Justification de chaque étape",
            "Notations correctes",
            "Présentation du résultat",
        ),
        duration_minutes=45,
        total_points=20,
        placeholder="Étape 1 : …",
    ),
    Subject.network.value: ExamFormat(
        label="Questions réseau",
        input_kind="text",
        method=(
            "Répondre question par question, en numérotant. Pour un calcul "
            "d'adressage, poser le détail (masque, adresse réseau, broadcast, "
            "plage utilisable)."
        ),
        criteria=(
            "Exactitude technique",
            "Détail des calculs d'adressage",
            "Vocabulaire technique précis",
            "Prise en compte des contraintes de l'énoncé",
            "Clarté des schémas décrits",
        ),
        duration_minutes=45,
        total_points=20,
        placeholder="1. …",
    ),
    Subject.security.value: ExamFormat(
        label="Analyse de sécurité",
        input_kind="text",
        method=(
            "Identifier la vulnérabilité, expliquer le mécanisme de l'attaque, "
            "proposer une remédiation concrète, et citer le cadre réglementaire "
            "quand il s'applique (RGPD)."
        ),
        criteria=(
            "Identification correcte de la faille",
            "Explication du mécanisme",
            "Pertinence de la remédiation",
            "Prise en compte réglementaire",
            "Hiérarchisation des risques",
        ),
        duration_minutes=45,
        total_points=20,
        placeholder="Vulnérabilité identifiée : …",
    ),
    Subject.english.value: ExamFormat(
        label="Written expression (English)",
        input_kind="text",
        method=(
            "Answer in English. Structure your answer: introduction, "
            "development, conclusion. Use technical IT vocabulary accurately."
        ),
        criteria=(
            "Task achievement",
            "Range and accuracy of technical vocabulary",
            "Grammatical accuracy",
            "Coherence and cohesion",
            "Register appropriate to the situation",
        ),
        duration_minutes=45,
        total_points=20,
        placeholder="Write your answer in English…",
    ),
}

# Repli pour les matières sans format d'épreuve défini.
DEFAULT_FORMAT = ExamFormat(
    label="Exercice",
    input_kind="text",
    method="Répondre de façon structurée et justifiée.",
    criteria=(
        "Exactitude",
        "Structure de la réponse",
        "Justification",
        "Clarté",
    ),
    duration_minutes=45,
    total_points=20,
    placeholder="Ta réponse…",
)


def format_for(subject: str) -> ExamFormat:
    return EXAM_FORMATS.get(subject, DEFAULT_FORMAT)
