"""
Moteur du graphe de connaissances.

Trois responsabilités :

  1. GARDER LE GRAPHE ACYCLIQUE
     Si `SQL` devient prérequis de `Jointures` et `Jointures` prérequis de
     `SQL`, aucun des deux ne sera jamais débloquable. On refuse donc toute
     arête créant un cycle (parcours en profondeur avant insertion).

  2. PROPAGER LA MAÎTRISE
     Chaque réponse à une carte fait bouger la maîtrise du nœud rattaché,
     par moyenne mobile exponentielle. Une seule bonne réponse ne suffit pas
     à passer « maîtrisé » ; une seule mauvaise ne détruit pas tout.

  3. DIAGNOSTIQUER
     C'est la fonctionnalité qui justifie tout le graphe : quand tu échoues
     sur une notion, remonter ses prérequis mal maîtrisés et te dire
     « tu ne comprends pas Doctrine parce que les relations SQL sont à 34 % ».
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EdgeRelation, NodeStatus, Rating
from app.models.graph import KnowledgeNode, NodeEdge

logger = logging.getLogger(__name__)

# ── Réglages pédagogiques ────────────────────────────────────────────────
# Poids d'une nouvelle performance dans la maîtrise. 0.25 → il faut ~4 bonnes
# réponses pour convaincre le système, ce qui filtre la chance.
MASTERY_ALPHA = 0.25

# Traduction d'une auto-évaluation en score de performance.
RATING_SCORE: dict[Rating, float] = {
    Rating.again: 0.0,
    Rating.hard: 0.5,
    Rating.good: 0.85,
    Rating.easy: 1.0,
}

MASTERED_THRESHOLD = 0.85   # au-dessus : maîtrisé
CRITICAL_THRESHOLD = 0.40   # en dessous, après plusieurs passages : critique
UNLOCK_THRESHOLD = 0.60     # maîtrise minimale d'un prérequis pour débloquer
WEAK_PREREQ_THRESHOLD = 0.60


# ═════════════════════════════════════════════════════════════════════════
#  1. Intégrité du graphe
# ═════════════════════════════════════════════════════════════════════════
async def _prerequisite_map(db: AsyncSession, user_id: int) -> dict[int, list[int]]:
    """{ node_id → [ids de ses prérequis] } pour tout le graphe d'un user."""
    rows = await db.execute(
        select(NodeEdge.source_id, NodeEdge.target_id).where(
            NodeEdge.user_id == user_id,
            NodeEdge.relation == EdgeRelation.prerequisite.value,
        )
    )
    prereqs: dict[int, list[int]] = defaultdict(list)
    for source_id, target_id in rows.all():
        prereqs[target_id].append(source_id)
    return prereqs


async def would_create_cycle(
    db: AsyncSession, user_id: int, source_id: int, target_id: int
) -> bool:
    """
    L'arête source → target créerait-elle un cycle ?

    Oui si `source` est déjà atteignable depuis `target` en suivant les arêtes
    de prérequis. On part de target et on remonte.
    """
    if source_id == target_id:
        return True

    prereqs = await _prerequisite_map(db, user_id)
    # `prereqs[x]` = ce dont x dépend. On cherche si target dépend de source
    # (auquel cas ajouter source→target bouclerait).
    stack = deque([target_id])
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current == source_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(prereqs.get(current, ()))
    return False


# ═════════════════════════════════════════════════════════════════════════
#  2. Propagation de la maîtrise
# ═════════════════════════════════════════════════════════════════════════
def apply_review_to_node(node: KnowledgeNode, rating: Rating) -> None:
    """
    Met à jour la maîtrise du nœud après une réponse. Modifie l'objet en place ;
    le commit est de la responsabilité de l'appelant.
    """
    score = RATING_SCORE[rating]
    node.mastery = round(
        node.mastery * (1 - MASTERY_ALPHA) + score * MASTERY_ALPHA, 4
    )
    node.review_count += 1
    if rating is Rating.again:
        node.failure_count += 1
    node.last_studied_at = datetime.now(UTC)
    node.status = derive_status(node).value


# Une copie d'examen pèse trois fois plus qu'une flashcard dans la maîtrise.
# C'est délibéré : réussir une carte prouve qu'on reconnaît une réponse, réussir
# une épreuve prouve qu'on sait mobiliser la notion sous contrainte de temps et
# de rédaction. Les deux signaux ne valent pas la même chose.
EXAM_ALPHA = MASTERY_ALPHA * 3


def apply_exam_result(node: KnowledgeNode, ratio: float) -> float:
    """
    Répercute une note d'examen sur la maîtrise d'une notion.

    Renvoie la variation de maîtrise — négative quand l'épreuve a révélé une
    faiblesse que les révisions ne montraient pas. C'est précisément le cas
    qui compte : bien réussir ses cartes et rater le sujet type BTS signifie
    que la notion est reconnue mais pas mobilisable.
    """
    before = node.mastery
    ratio = max(0.0, min(1.0, ratio))
    node.mastery = round(node.mastery * (1 - EXAM_ALPHA) + ratio * EXAM_ALPHA, 4)
    node.review_count += 1
    if ratio < 0.5:
        node.failure_count += 1
    node.last_studied_at = datetime.now(UTC)
    node.status = derive_status(node).value
    return round(node.mastery - before, 4)


def derive_status(node: KnowledgeNode) -> NodeStatus:
    """
    Statut affiché dans le Skill Tree. Ne gère pas `locked` : ça dépend des
    prérequis, donc du graphe entier (voir `recompute_locks`).
    """
    if node.mastery >= MASTERED_THRESHOLD:
        return NodeStatus.mastered
    # « critique » exige des données : sinon toute notion neuve serait rouge.
    if node.mastery < CRITICAL_THRESHOLD and node.review_count >= 3:
        return NodeStatus.critical
    if node.review_count == 0:
        return NodeStatus.available
    return NodeStatus.learning


async def recompute_locks(db: AsyncSession, user_id: int) -> int:
    """
    Recalcule le verrouillage de tous les nœuds. Un nœud est `locked` si au
    moins un de ses prérequis est sous le seuil `UNLOCK_THRESHOLD`.

    Renvoie le nombre de nœuds dont le statut a changé.
    """
    nodes = (
        await db.execute(select(KnowledgeNode).where(KnowledgeNode.user_id == user_id))
    ).scalars().all()
    by_id = {n.id: n for n in nodes}
    prereqs = await _prerequisite_map(db, user_id)

    changed = 0
    for node in nodes:
        blocking = [
            by_id[pid]
            for pid in prereqs.get(node.id, ())
            if pid in by_id and by_id[pid].mastery < UNLOCK_THRESHOLD
        ]
        new_status = (
            NodeStatus.locked.value
            if blocking and node.review_count == 0
            else derive_status(node).value
        )
        if new_status != node.status:
            node.status = new_status
            changed += 1
    return changed


# ═════════════════════════════════════════════════════════════════════════
#  3. Diagnostic
# ═════════════════════════════════════════════════════════════════════════
async def weak_prerequisites(
    db: AsyncSession,
    user_id: int,
    node_id: int,
    *,
    threshold: float = WEAK_PREREQ_THRESHOLD,
    max_depth: int = 3,
) -> list[KnowledgeNode]:
    """
    Prérequis mal maîtrisés d'un nœud, du plus faible au moins faible.

    Remonte jusqu'à `max_depth` niveaux : si tu échoues sur Doctrine, la cause
    peut être « relations SQL » (niveau 1) ou « clés étrangères » (niveau 2).
    """
    prereqs = await _prerequisite_map(db, user_id)

    to_visit: list[tuple[int, int]] = [(node_id, 0)]
    collected: set[int] = set()
    seen: set[int] = {node_id}

    while to_visit:
        current, depth = to_visit.pop()
        if depth >= max_depth:
            continue
        for pid in prereqs.get(current, ()):
            collected.add(pid)
            if pid not in seen:
                seen.add(pid)
                to_visit.append((pid, depth + 1))

    if not collected:
        return []

    rows = await db.execute(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.id.in_(collected),
            KnowledgeNode.mastery < threshold,
        )
        .order_by(KnowledgeNode.mastery.asc())
    )
    return list(rows.scalars().all())


# Demi-vie de la maîtrise d'une notion laissée de côté. À 90 jours, une notion
# à 80 % retombe à 40 % si elle n'est pas retravaillée.
#
# Pourquoi c'est nécessaire : la maîtrise stockée est un instantané. Sans
# décroissance, une notion validée il y a six mois reste affichée à 90 % et
# n'est jamais reproposée — alors que c'est précisément celle qu'on a oubliée.
# Le SRS gère l'oubli au niveau des CARTES ; rien ne le gérait au niveau des
# NOTIONS.
MASTERY_HALF_LIFE_DAYS = 90.0


def effective_mastery(node: KnowledgeNode, now: datetime | None = None) -> float:
    """
    Maîtrise corrigée de l'oubli écoulé depuis la dernière séance.

    Ne modifie rien en base : c'est une lecture. La valeur stockée reste la
    performance réellement constatée, la valeur effective sert à décider quoi
    proposer aujourd'hui.
    """
    if not node.last_studied_at or node.mastery <= 0:
        return node.mastery

    now = now or datetime.now(UTC)
    elapsed = (now - node.last_studied_at).total_seconds() / 86400.0
    if elapsed <= 0:
        return node.mastery

    import math

    return round(node.mastery * math.exp(-elapsed / MASTERY_HALF_LIFE_DAYS), 4)


async def recommended_nodes(
    db: AsyncSession, user_id: int, *, limit: int = 5
) -> list[KnowledgeNode]:
    """
    Prochaines notions à travailler, triées par priorité.

    Score = (1 − maîtrise effective) × urgence
      • la maîtrise EFFECTIVE tient compte du temps écoulé : une notion à 85 %
        travaillée il y a six mois vaut moins qu'une notion à 70 % revue hier.
      • urgence : ×2 pour un nœud `critical` (régression détectée), ×1.4 pour
        un nœud `learning` (déjà entamé, on finit avant d'ouvrir un front),
        ×1 sinon. Les nœuds `locked` sont exclus : les attaquer sans leurs
        prérequis est le meilleur moyen de perdre son temps.
    """
    rows = await db.execute(
        select(KnowledgeNode).where(
            KnowledgeNode.user_id == user_id,
            KnowledgeNode.status != NodeStatus.locked.value,
            KnowledgeNode.mastery < MASTERED_THRESHOLD,
        )
    )
    nodes = list(rows.scalars().all())

    urgency = {
        NodeStatus.critical.value: 2.0,
        NodeStatus.learning.value: 1.4,
    }
    now = datetime.now(UTC)
    nodes.sort(
        key=lambda n: (1 - effective_mastery(n, now)) * urgency.get(n.status, 1.0),
        reverse=True,
    )
    return nodes[:limit]


async def graph_snapshot(db: AsyncSession, user_id: int) -> dict:
    """Nœuds + arêtes pour la visualisation frontend (React Flow)."""
    nodes = (
        await db.execute(
            select(KnowledgeNode)
            .where(KnowledgeNode.user_id == user_id)
            .order_by(KnowledgeNode.subject, KnowledgeNode.title)
        )
    ).scalars().all()
    edges = (
        await db.execute(select(NodeEdge).where(NodeEdge.user_id == user_id))
    ).scalars().all()
    return {"nodes": list(nodes), "edges": list(edges)}
