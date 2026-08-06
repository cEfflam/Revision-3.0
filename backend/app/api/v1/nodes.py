"""
Graphe de connaissances — nœuds, arêtes, diagnostic.

Attention à l'ordre de déclaration : `/nodes/graph` doit être défini AVANT
`/nodes/{node_id}`. FastAPI teste les routes dans l'ordre ; déclaré après,
« graph » serait interprété comme un `node_id` et renverrait une erreur de
validation au lieu du graphe.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.utils import slugify
from app.models.enums import EdgeRelation, NodeStatus, Subject
from app.models.graph import KnowledgeNode, NodeEdge
from app.schemas.graph import (
    DiagnosisRead,
    EdgeCreate,
    EdgeRead,
    GraphRead,
    NodeCreate,
    NodeRead,
    NodeUpdate,
)
from app.services.graph import engine as graph_engine

router = APIRouter(prefix="/nodes", tags=["graphe"])


async def _set_parent(
    db, user, node: KnowledgeNode, parent_id: int | None
) -> None:
    """
    Range une notion sous un thème, ou l'en sort si `parent_id` vaut None.

    Refuse tout cycle : rattacher un thème sous l'un de ses propres
    descendants détacherait toute la branche de l'arbre, sans erreur visible
    — elle disparaîtrait simplement de l'affichage.
    """
    if parent_id is None:
        node.parent_id = None
        return

    if parent_id == node.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Une notion ne peut pas être son propre thème.",
        )

    parent = await db.get(KnowledgeNode, parent_id)
    if parent is None or parent.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Thème introuvable."
        )

    # Remonte la chaîne des parents : si on retombe sur `node`, c'est un cycle.
    ancestor = parent
    seen: set[int] = set()
    while ancestor is not None and ancestor.parent_id is not None:
        if ancestor.parent_id == node.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"« {parent.title} » est déjà rangé sous « {node.title} ». "
                    "Ce déplacement détacherait la branche de l'arbre."
                ),
            )
        if ancestor.id in seen:
            break
        seen.add(ancestor.id)
        ancestor = await db.get(KnowledgeNode, ancestor.parent_id)

    node.parent_id = parent_id


async def _get_owned_node(db, user, node_id: int) -> KnowledgeNode:
    node = await db.get(KnowledgeNode, node_id)
    # Le contrôle de propriété est fait ici, systématiquement : sans lui, un
    # utilisateur pourrait lire le graphe d'un autre en devinant un id.
    if node is None or node.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notion introuvable."
        )
    return node


# ═════════════════════════════════════════════════════════════════════════
#  Routes statiques (avant les routes paramétrées)
# ═════════════════════════════════════════════════════════════════════════
@router.get("/graph", response_model=GraphRead, summary="Graphe complet")
async def read_graph(user: CurrentUser, db: DbSession) -> GraphRead:
    snapshot = await graph_engine.graph_snapshot(db, user.id)
    nodes = snapshot["nodes"]

    counts: dict[str, int] = {s.value: 0 for s in NodeStatus}
    for node in nodes:
        counts[node.status] = counts.get(node.status, 0) + 1
    counts["total"] = len(nodes)

    return GraphRead(
        nodes=[NodeRead.model_validate(n) for n in nodes],
        edges=[EdgeRead.model_validate(e) for e in snapshot["edges"]],
        counts=counts,
    )


@router.get(
    "/recommended",
    response_model=list[NodeRead],
    summary="Prochaines notions à travailler",
)
async def read_recommended(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=5, ge=1, le=20),
) -> list[NodeRead]:
    nodes = await graph_engine.recommended_nodes(db, user.id, limit=limit)
    return [NodeRead.model_validate(n) for n in nodes]


@router.post(
    "/edges",
    response_model=EdgeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une dépendance entre deux notions",
)
async def create_edge(
    payload: EdgeCreate, user: CurrentUser, db: DbSession
) -> EdgeRead:
    source = await _get_owned_node(db, user, payload.source_id)
    target = await _get_owned_node(db, user, payload.target_id)

    if payload.relation is EdgeRelation.prerequisite and await graph_engine.would_create_cycle(
        db, user.id, source.id, target.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"« {source.title} » dépend déjà (directement ou non) de "
                f"« {target.title} ». Cette arête créerait un cycle : aucune des "
                "deux notions ne pourrait plus être débloquée."
            ),
        )

    duplicate = (
        await db.execute(
            select(NodeEdge).where(
                NodeEdge.source_id == source.id,
                NodeEdge.target_id == target.id,
                NodeEdge.relation == payload.relation.value,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        return EdgeRead.model_validate(duplicate)

    edge = NodeEdge(
        user_id=user.id,
        source_id=source.id,
        target_id=target.id,
        relation=payload.relation.value,
        weight=payload.weight,
    )
    db.add(edge)
    await db.flush()
    await graph_engine.recompute_locks(db, user.id)
    await db.commit()
    await db.refresh(edge)
    return EdgeRead.model_validate(edge)


@router.delete(
    "/edges/{edge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une dépendance",
)
async def delete_edge(edge_id: int, user: CurrentUser, db: DbSession) -> None:
    edge = await db.get(NodeEdge, edge_id)
    if edge is None or edge.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dépendance introuvable."
        )
    await db.delete(edge)
    await db.flush()
    await graph_engine.recompute_locks(db, user.id)
    await db.commit()


# ═════════════════════════════════════════════════════════════════════════
#  CRUD des nœuds
# ═════════════════════════════════════════════════════════════════════════
@router.get("", response_model=list[NodeRead], summary="Lister mes notions")
async def list_nodes(
    user: CurrentUser,
    db: DbSession,
    subject: Subject | None = None,
    node_status: NodeStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[NodeRead]:
    stmt = select(KnowledgeNode).where(KnowledgeNode.user_id == user.id)
    if subject:
        stmt = stmt.where(KnowledgeNode.subject == subject.value)
    if node_status:
        stmt = stmt.where(KnowledgeNode.status == node_status.value)

    rows = await db.execute(
        stmt.order_by(
            KnowledgeNode.subject, KnowledgeNode.mastery, KnowledgeNode.title
        ).limit(limit)
    )
    return [NodeRead.model_validate(n) for n in rows.scalars().all()]


@router.post(
    "",
    response_model=NodeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une notion",
)
async def create_node(
    payload: NodeCreate, user: CurrentUser, db: DbSession
) -> NodeRead:
    slug = payload.slug or slugify(payload.title)

    if (
        await db.execute(
            select(KnowledgeNode.id).where(
                KnowledgeNode.user_id == user.id, KnowledgeNode.slug == slug
            )
        )
    ).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Une notion avec le slug « {slug} » existe déjà.",
        )

    node = KnowledgeNode(
        user_id=user.id,
        slug=slug,
        title=payload.title.strip(),
        kind=payload.kind.value,
        subject=payload.subject.value,
        description=payload.description.strip(),
        difficulty=payload.difficulty,
        estimated_minutes=payload.estimated_minutes,
        position=payload.position,
    )
    db.add(node)
    await db.flush()

    if payload.parent_id is not None:
        await _set_parent(db, user, node, payload.parent_id)

    # Les prérequis sont fournis par slug : plus pratique à écrire à la main et
    # stable si les identifiants changent.
    if payload.prerequisites:
        sources = (
            await db.execute(
                select(KnowledgeNode).where(
                    KnowledgeNode.user_id == user.id,
                    KnowledgeNode.slug.in_(payload.prerequisites),
                )
            )
        ).scalars().all()
        found = {s.slug for s in sources}
        missing = set(payload.prerequisites) - found
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prérequis inconnus : {', '.join(sorted(missing))}.",
            )
        for source in sources:
            if await graph_engine.would_create_cycle(db, user.id, source.id, node.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Le prérequis « {source.slug} » créerait un cycle.",
                )
            db.add(
                NodeEdge(
                    user_id=user.id,
                    source_id=source.id,
                    target_id=node.id,
                    relation=EdgeRelation.prerequisite.value,
                )
            )
        await db.flush()

    await graph_engine.recompute_locks(db, user.id)
    await db.commit()
    await db.refresh(node)
    return NodeRead.model_validate(node)


@router.get("/{node_id}", response_model=NodeRead, summary="Détail d'une notion")
async def read_node(node_id: int, user: CurrentUser, db: DbSession) -> NodeRead:
    return NodeRead.model_validate(await _get_owned_node(db, user, node_id))


@router.patch("/{node_id}", response_model=NodeRead, summary="Modifier une notion")
async def update_node(
    node_id: int, payload: NodeUpdate, user: CurrentUser, db: DbSession
) -> NodeRead:
    node = await _get_owned_node(db, user, node_id)

    data = payload.model_dump(exclude_unset=True)

    # `parent_id` est le seul champ dont `None` est une valeur signifiante :
    # elle sort la notion de son thème pour la remettre « à classer ».
    if "parent_id" in data:
        await _set_parent(db, user, node, data.pop("parent_id"))

    for field_name, value in data.items():
        if value is None:
            continue
        if field_name in {"kind", "subject"}:
            setattr(node, field_name, value.value if hasattr(value, "value") else value)
        else:
            setattr(node, field_name, value)

    if "mastery" in data:
        node.status = graph_engine.derive_status(node).value
        await graph_engine.recompute_locks(db, user.id)

    await db.commit()
    await db.refresh(node)
    return NodeRead.model_validate(node)


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une notion",
)
async def delete_node(node_id: int, user: CurrentUser, db: DbSession) -> None:
    node = await _get_owned_node(db, user, node_id)
    await db.delete(node)
    await db.flush()
    await graph_engine.recompute_locks(db, user.id)
    await db.commit()


@router.get(
    "/{node_id}/diagnosis",
    response_model=DiagnosisRead,
    summary="Pourquoi je bloque sur cette notion ?",
)
async def diagnose_node(
    node_id: int, user: CurrentUser, db: DbSession
) -> DiagnosisRead:
    """
    La fonctionnalité qui justifie tout le graphe : au lieu de « tu as échoué »,
    l'application remonte la cause probable dans les prérequis.
    """
    node = await _get_owned_node(db, user, node_id)
    weak = await graph_engine.weak_prerequisites(db, user.id, node.id)

    if not weak:
        verdict = (
            f"Aucun prérequis faible détecté pour « {node.title} ». "
            "La difficulté vient de la notion elle-même : reprends-la "
            "directement, avec un exercice guidé."
        )
    else:
        worst = weak[0]
        verdict = (
            f"« {node.title} » bloque probablement à cause de "
            f"« {worst.title} » ({worst.mastery:.0%} de maîtrise). "
            f"Travaille ce prérequis d'abord : {len(weak)} notion(s) en amont "
            "sont encore fragiles."
        )

    return DiagnosisRead(
        node=NodeRead.model_validate(node),
        weak_prerequisites=[NodeRead.model_validate(n) for n in weak],
        verdict=verdict,
    )
