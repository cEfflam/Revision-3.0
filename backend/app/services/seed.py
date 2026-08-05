"""
Graphe de compétences BTS SIO de démarrage.

Pourquoi le pré-câbler au lieu de le faire générer par l'IA ? Parce que les
dépendances entre notions d'un référentiel ne s'inventent pas : « Doctrine
dépend des jointures SQL » est un fait pédagogique, pas une opinion. Autant
l'écrire une fois correctement. L'IA prendra le relais pour enrichir le graphe
à partir de TES documents, là où elle apporte réellement quelque chose.

Le graphe reste un DAG : chaque `prerequisites` ne référence que des slugs
déclarés plus haut dans la liste. Cette contrainte d'ordre est vérifiée au
démarrage par le test d'intégrité en fin de fichier.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EdgeRelation, NodeKind, Subject
from app.models.graph import KnowledgeNode, NodeEdge
from app.models.user import User
from app.services.graph import engine as graph_engine

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NodeSeed:
    slug: str
    title: str
    subject: Subject
    kind: NodeKind = NodeKind.concept
    difficulty: int = 3
    minutes: int = 20
    prerequisites: list[str] = field(default_factory=list)


# ── SQL & bases de données ───────────────────────────────────────────────
_SQL = [
    NodeSeed("sql-bases", "Modèle relationnel", Subject.sql, NodeKind.domain, 2, 30),
    NodeSeed("sql-select", "SELECT / FROM / WHERE", Subject.sql, NodeKind.skill, 1, 25,
             ["sql-bases"]),
    NodeSeed("sql-cle-primaire", "Clé primaire", Subject.sql, NodeKind.concept, 1, 15,
             ["sql-bases"]),
    NodeSeed("sql-cle-etrangere", "Clé étrangère", Subject.sql, NodeKind.concept, 2, 20,
             ["sql-cle-primaire"]),
    NodeSeed("sql-agregats", "Fonctions d'agrégation", Subject.sql, NodeKind.skill, 2, 20,
             ["sql-select"]),
    NodeSeed("sql-group-by", "GROUP BY / HAVING", Subject.sql, NodeKind.skill, 3, 25,
             ["sql-agregats"]),
    NodeSeed("sql-jointures-internes", "INNER JOIN", Subject.sql, NodeKind.skill, 3, 30,
             ["sql-select", "sql-cle-etrangere"]),
    NodeSeed("sql-jointures-externes", "LEFT / RIGHT JOIN", Subject.sql, NodeKind.skill, 3, 25,
             ["sql-jointures-internes"]),
    NodeSeed("sql-sous-requetes", "Sous-requêtes", Subject.sql, NodeKind.skill, 4, 30,
             ["sql-jointures-internes"]),
    NodeSeed("sql-transactions", "Transactions et ACID", Subject.sql, NodeKind.concept, 3, 25,
             ["sql-bases"]),
    NodeSeed("sql-index", "Index et performance", Subject.sql, NodeKind.skill, 4, 30,
             ["sql-jointures-internes"]),
]

# ── Développement ────────────────────────────────────────────────────────
_DEV = [
    NodeSeed("dev-algo", "Algorithmique", Subject.dev, NodeKind.domain, 2, 40),
    NodeSeed("dev-git", "Git et versionnement", Subject.dev, NodeKind.skill, 2, 30),
    NodeSeed("dev-php", "PHP", Subject.dev, NodeKind.topic, 2, 40, ["dev-algo"]),
    NodeSeed("dev-poo", "Programmation orientée objet", Subject.dev, NodeKind.topic, 3, 45,
             ["dev-algo"]),
    NodeSeed("dev-mvc", "Architecture MVC", Subject.dev, NodeKind.concept, 3, 30,
             ["dev-poo"]),
    NodeSeed("dev-tests", "Tests unitaires", Subject.dev, NodeKind.skill, 3, 30,
             ["dev-poo"]),
    NodeSeed("dev-symfony", "Symfony", Subject.dev, NodeKind.topic, 4, 60,
             ["dev-mvc", "dev-php"]),
    NodeSeed("dev-api-rest", "API REST", Subject.dev, NodeKind.skill, 3, 40,
             ["dev-mvc"]),
    # Le nœud emblématique : trois prérequis, dont un dans une autre matière.
    NodeSeed("dev-doctrine", "Doctrine ORM", Subject.dev, NodeKind.topic, 4, 50,
             ["dev-symfony", "dev-poo", "sql-jointures-internes"]),
    NodeSeed("dev-doctrine-relations", "Relations Doctrine", Subject.dev, NodeKind.skill, 5, 45,
             ["dev-doctrine", "sql-jointures-externes"]),
]

# ── Réseau & systèmes ────────────────────────────────────────────────────
_NET = [
    NodeSeed("net-osi", "Modèle OSI", Subject.network, NodeKind.domain, 2, 30),
    NodeSeed("net-tcp-ip", "Pile TCP/IP", Subject.network, NodeKind.topic, 3, 35,
             ["net-osi"]),
    NodeSeed("net-adressage-ip", "Adressage IP et masques", Subject.network, NodeKind.skill, 3, 40,
             ["net-tcp-ip"]),
    NodeSeed("net-routage", "Routage", Subject.network, NodeKind.skill, 4, 40,
             ["net-adressage-ip"]),
    NodeSeed("net-dhcp", "DHCP", Subject.network, NodeKind.concept, 2, 20,
             ["net-adressage-ip"]),
    NodeSeed("net-dns", "DNS", Subject.network, NodeKind.concept, 2, 25,
             ["net-adressage-ip"]),
    NodeSeed("net-vlan", "VLAN", Subject.network, NodeKind.concept, 4, 30,
             ["net-adressage-ip"]),
    NodeSeed("net-linux", "Administration Linux", Subject.network, NodeKind.topic, 3, 50),
]

# ── Cybersécurité ────────────────────────────────────────────────────────
_SEC = [
    NodeSeed("sec-rgpd", "RGPD", Subject.security, NodeKind.topic, 2, 30),
    NodeSeed("sec-https", "TLS / HTTPS", Subject.security, NodeKind.concept, 3, 30,
             ["net-tcp-ip"]),
    NodeSeed("sec-injection-sql", "Injection SQL", Subject.security, NodeKind.concept, 3, 30,
             ["sql-select", "dev-php"]),
    NodeSeed("sec-xss", "XSS", Subject.security, NodeKind.concept, 3, 25, ["dev-php"]),
    NodeSeed("sec-auth", "Authentification", Subject.security, NodeKind.skill, 3, 35,
             ["dev-api-rest"]),
    NodeSeed("sec-jwt", "JWT", Subject.security, NodeKind.concept, 4, 30, ["sec-auth"]),
]

# ── Mathématiques ────────────────────────────────────────────────────────
_MATH = [
    NodeSeed("math-logique", "Logique et ensembles", Subject.math, NodeKind.domain, 2, 30),
    NodeSeed("math-suites", "Suites numériques", Subject.math, NodeKind.topic, 3, 40,
             ["math-logique"]),
    NodeSeed("math-proba", "Probabilités", Subject.math, NodeKind.topic, 3, 40,
             ["math-logique"]),
    NodeSeed("math-graphes", "Théorie des graphes", Subject.math, NodeKind.topic, 3, 35,
             ["math-logique"]),
    NodeSeed("math-arithmetique", "Arithmétique et cryptographie", Subject.math, NodeKind.topic, 4, 40,
             ["math-logique"]),
]

# ── CEJM ─────────────────────────────────────────────────────────────────
_CEJM = [
    NodeSeed("cejm-methodo", "Méthodologie du cas pratique", Subject.cejm, NodeKind.domain, 2, 30),
    NodeSeed("cejm-contrat", "Le contrat", Subject.cejm, NodeKind.topic, 3, 35,
             ["cejm-methodo"]),
    NodeSeed("cejm-marche", "Marché et concurrence", Subject.cejm, NodeKind.topic, 3, 35,
             ["cejm-methodo"]),
    NodeSeed("cejm-management", "Management et structures", Subject.cejm, NodeKind.topic, 3, 35,
             ["cejm-methodo"]),
    NodeSeed("cejm-droit-numerique", "Droit du numérique", Subject.cejm, NodeKind.topic, 3, 35,
             ["cejm-contrat"]),
]

# ── Culture générale et expression ───────────────────────────────────────
_CGE = [
    NodeSeed("cge-synthese", "Méthode de la synthèse", Subject.cge, NodeKind.domain, 3, 45),
    NodeSeed("cge-argumentation", "Argumentation", Subject.cge, NodeKind.skill, 3, 35,
             ["cge-synthese"]),
    NodeSeed("cge-ecriture-perso", "Écriture personnelle", Subject.cge, NodeKind.skill, 4, 45,
             ["cge-argumentation"]),
]

# ── Anglais ──────────────────────────────────────────────────────────────
_EN = [
    NodeSeed("en-vocab-it", "Vocabulaire technique IT", Subject.english, NodeKind.domain, 2, 25),
    NodeSeed("en-comprehension", "Compréhension de documents", Subject.english, NodeKind.skill, 3, 30,
             ["en-vocab-it"]),
    NodeSeed("en-expression", "Expression orale et écrite", Subject.english, NodeKind.skill, 3, 30,
             ["en-vocab-it"]),
]

BTS_SIO_CURRICULUM: list[NodeSeed] = [
    *_SQL, *_DEV, *_NET, *_SEC, *_MATH, *_CEJM, *_CGE, *_EN
]


def validate_curriculum(curriculum: list[NodeSeed] | None = None) -> None:
    """
    Vérifie qu'aucun prérequis ne pointe vers un slug inconnu ou déclaré plus
    loin dans la liste. L'ordre garantit l'absence de cycle : impossible qu'une
    notion dépende d'une notion qui dépend d'elle.
    """
    curriculum = curriculum or BTS_SIO_CURRICULUM
    seen: set[str] = set()
    for node in curriculum:
        for prerequisite in node.prerequisites:
            if prerequisite not in seen:
                raise ValueError(
                    f"Prérequis « {prerequisite} » de « {node.slug} » inconnu ou "
                    "déclaré après lui — le graphe ne serait plus acyclique."
                )
        if node.slug in seen:
            raise ValueError(f"Slug dupliqué : {node.slug}")
        seen.add(node.slug)


# Le référentiel est validé à l'import : une faute de frappe est repérée au
# démarrage du backend, pas au premier onboarding d'un utilisateur.
validate_curriculum()


# Un niveau déclaré n'est pas un niveau démontré. On n'accorde donc que la
# moitié du crédit annoncé : assez pour ne pas faire réviser les bases à
# quelqu'un d'expérimenté, pas assez pour marquer « maîtrisé » sans preuve.
DECLARED_LEVEL_CREDIT = 0.5


async def seed_curriculum(
    db: AsyncSession,
    user: User,
    *,
    assessments: dict[str, int] | None = None,
    curriculum: list[NodeSeed] | None = None,
) -> int:
    """
    Crée le graphe de départ pour un utilisateur. Idempotent : les nœuds déjà
    présents (même slug) sont ignorés, jamais écrasés.

    Renvoie le nombre de nœuds créés. Ne commit pas.
    """
    curriculum = curriculum or BTS_SIO_CURRICULUM
    assessments = assessments or {}

    existing_slugs = set(
        (
            await db.execute(
                select(KnowledgeNode.slug).where(KnowledgeNode.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )

    by_slug: dict[str, KnowledgeNode] = {}
    created = 0

    for seed in curriculum:
        if seed.slug in existing_slugs:
            continue
        mastery = round(
            (assessments.get(seed.subject.value, 0) / 100.0) * DECLARED_LEVEL_CREDIT, 4
        )
        node = KnowledgeNode(
            user_id=user.id,
            slug=seed.slug,
            title=seed.title,
            kind=seed.kind.value,
            subject=seed.subject.value,
            difficulty=seed.difficulty,
            estimated_minutes=seed.minutes,
            mastery=mastery,
        )
        db.add(node)
        by_slug[seed.slug] = node
        created += 1

    if not created:
        return 0

    # flush pour obtenir les identifiants avant de créer les arêtes.
    await db.flush()

    # Les nœuds préexistants sont récupérés pour pouvoir raccrocher les arêtes
    # d'un ajout partiel de référentiel.
    if existing_slugs:
        rows = await db.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.user_id == user.id,
                KnowledgeNode.slug.in_(existing_slugs),
            )
        )
        for node in rows.scalars().all():
            by_slug.setdefault(node.slug, node)

    for seed in curriculum:
        target = by_slug.get(seed.slug)
        if target is None:
            continue
        for prerequisite_slug in seed.prerequisites:
            source = by_slug.get(prerequisite_slug)
            if source is None:
                logger.warning(
                    "Prérequis %s introuvable pour %s", prerequisite_slug, seed.slug
                )
                continue
            db.add(
                NodeEdge(
                    user_id=user.id,
                    source_id=source.id,
                    target_id=target.id,
                    relation=EdgeRelation.prerequisite.value,
                )
            )

    await db.flush()
    await graph_engine.recompute_locks(db, user.id)
    logger.info("Graphe initialisé : %s nœuds pour l'utilisateur %s", created, user.id)
    return created
