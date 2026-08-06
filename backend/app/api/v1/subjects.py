"""
Vue par matière — « je veux travailler les maths maintenant ».

Le dashboard décide à ta place (et c'est bien pour la routine quotidienne).
Cet écran fait l'inverse : il te laisse choisir ton angle d'attaque, puis
concentre au même endroit tout ce qui existe sur cette matière — notions,
points faibles, cours importés, cartes à réviser.

Les agrégats sont calculés en SQL groupé plutôt qu'en bouclant sur les
matières : une requête par métrique, pas onze.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, func, select

from app.core.deps import CurrentUser, DbSession
from app.models.content import Document, document_nodes
from app.models.enums import SUBJECT_LABELS, NodeKind, NodeStatus, Subject
from app.models.graph import KnowledgeNode
from app.models.learning import Card
from app.schemas.content import DocumentRead
from app.schemas.graph import CurriculumNode, CurriculumRead, NodeRead
from app.schemas.subject import SubjectDetail, SubjectSummary
from app.services.graph.engine import MASTERED_THRESHOLD

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subjects", tags=["matières"])


def _rows_to_map(rows) -> dict[str, int]:
    return {str(key): int(value or 0) for key, value in rows}


async def _counts_by_subject(db, stmt: Select) -> dict[str, int]:
    return _rows_to_map((await db.execute(stmt)).all())


@router.get("", response_model=list[SubjectSummary], summary="Toutes mes matières")
async def list_subjects(user: CurrentUser, db: DbSession) -> list[SubjectSummary]:
    """
    Une tuile par matière possédant au moins une notion.

    Trié par maîtrise croissante : la matière la plus fragile arrive en tête,
    parce que c'est celle qu'il faut travailler.
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    mastery_rows = (
        await db.execute(
            select(
                KnowledgeNode.subject,
                func.avg(KnowledgeNode.mastery),
                func.count(KnowledgeNode.id),
            )
            .where(KnowledgeNode.user_id == user.id)
            .group_by(KnowledgeNode.subject)
        )
    ).all()

    mastered = await _counts_by_subject(
        db,
        select(KnowledgeNode.subject, func.count(KnowledgeNode.id))
        .where(
            KnowledgeNode.user_id == user.id,
            KnowledgeNode.status == NodeStatus.mastered.value,
        )
        .group_by(KnowledgeNode.subject),
    )
    critical = await _counts_by_subject(
        db,
        select(KnowledgeNode.subject, func.count(KnowledgeNode.id))
        .where(
            KnowledgeNode.user_id == user.id,
            KnowledgeNode.status == NodeStatus.critical.value,
        )
        .group_by(KnowledgeNode.subject),
    )
    documents = await _counts_by_subject(
        db,
        select(Document.subject, func.count(Document.id))
        .where(Document.user_id == user.id)
        .group_by(Document.subject),
    )

    # Les cartes ne portent pas de matière : elle vient du nœud rattaché.
    cards_total = await _counts_by_subject(
        db,
        select(KnowledgeNode.subject, func.count(Card.id))
        .join(KnowledgeNode, Card.node_id == KnowledgeNode.id)
        .where(Card.user_id == user.id)
        .group_by(KnowledgeNode.subject),
    )
    cards_due = await _counts_by_subject(
        db,
        select(KnowledgeNode.subject, func.count(Card.id))
        .join(KnowledgeNode, Card.node_id == KnowledgeNode.id)
        .where(
            Card.user_id == user.id,
            Card.is_suspended.is_(False),
            Card.due_at <= now,
        )
        .group_by(KnowledgeNode.subject),
    )

    summaries = [
        SubjectSummary(
            subject=str(subject),
            label=SUBJECT_LABELS.get(str(subject), str(subject)),
            mastery=round(float(average or 0.0), 4),
            nodes_total=int(total),
            nodes_mastered=mastered.get(str(subject), 0),
            nodes_critical=critical.get(str(subject), 0),
            cards_total=cards_total.get(str(subject), 0),
            cards_due=cards_due.get(str(subject), 0),
            documents_total=documents.get(str(subject), 0),
        )
        for subject, average, total in mastery_rows
    ]
    summaries.sort(key=lambda s: s.mastery)
    return summaries


@router.get(
    "/{subject}/curriculum",
    response_model=CurriculumRead,
    summary="Mon référentiel pour cette matière",
)
async def read_curriculum(
    subject: Subject, user: CurrentUser, db: DbSession
) -> CurriculumRead:
    """
    L'arbre du référentiel : Thème > Notion, tel que TU l'as écrit.

    Rien n'est généré ici. C'est la différence de fond avec une extraction
    automatique depuis des PDF : le programme du BTS est fixe et connu, donc
    l'écrire une fois vaut mieux que le deviner à chaque import — deviner
    produit des doublons et une granularité incohérente.
    """
    nodes = (
        await db.execute(
            select(KnowledgeNode)
            .where(
                KnowledgeNode.user_id == user.id,
                KnowledgeNode.subject == subject.value,
            )
            .order_by(KnowledgeNode.position, KnowledgeNode.title)
        )
    ).scalars().all()

    documents_per_node = _rows_to_map(
        (
            await db.execute(
                select(document_nodes.c.node_id, func.count())
                .group_by(document_nodes.c.node_id)
            )
        ).all()
    )
    cards_per_node = _rows_to_map(
        (
            await db.execute(
                select(Card.node_id, func.count(Card.id))
                .where(Card.user_id == user.id, Card.node_id.is_not(None))
                .group_by(Card.node_id)
            )
        ).all()
    )

    def to_tree(node: KnowledgeNode) -> CurriculumNode:
        # On passe par NodeRead — qui n'a pas de champ `children` — puis on
        # greffe les enfants déjà chargés. Valider directement l'objet ORM
        # ferait tenter à Pydantic un chargement paresseux de la relation,
        # impossible hors du contexte asynchrone (MissingGreenlet).
        return CurriculumNode(
            **NodeRead.model_validate(node).model_dump(),
            documents_count=documents_per_node.get(str(node.id), 0),
            cards_count=cards_per_node.get(str(node.id), 0),
            children=[
                to_tree(child) for child in children_by_parent.get(node.id, [])
            ],
        )

    children_by_parent: dict[int, list[KnowledgeNode]] = {}
    for node in nodes:
        if node.parent_id is not None:
            children_by_parent.setdefault(node.parent_id, []).append(node)

    roots = [n for n in nodes if n.parent_id is None]
    themes = [to_tree(n) for n in roots if n.kind != NodeKind.concept.value]
    # Une notion sans thème parent n'est pas perdue : elle remonte dans
    # « à classer » pour que le trou soit visible plutôt que silencieux.
    orphans = [to_tree(n) for n in roots if n.kind == NodeKind.concept.value]

    return CurriculumRead(
        subject=subject.value,
        label=SUBJECT_LABELS.get(subject.value, subject.value),
        themes=themes,
        orphans=orphans,
    )


@router.get(
    "/{subject}", response_model=SubjectDetail, summary="Tout sur une matière"
)
async def read_subject(
    subject: Subject, user: CurrentUser, db: DbSession
) -> SubjectDetail:
    nodes = (
        await db.execute(
            select(KnowledgeNode)
            .where(
                KnowledgeNode.user_id == user.id,
                KnowledgeNode.subject == subject.value,
            )
            .order_by(KnowledgeNode.mastery.asc(), KnowledgeNode.title)
        )
    ).scalars().all()

    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Aucune notion en « {SUBJECT_LABELS.get(subject.value, subject.value)} ». "
                "Passe par l'onboarding ou importe un cours."
            ),
        )

    documents = (
        await db.execute(
            select(Document)
            .where(Document.user_id == user.id, Document.subject == subject.value)
            .order_by(Document.created_at.desc())
        )
    ).scalars().all()

    summaries = await list_subjects(user, db)
    summary = next(
        (s for s in summaries if s.subject == subject.value),
        SubjectSummary(
            subject=subject.value,
            label=SUBJECT_LABELS.get(subject.value, subject.value),
        ),
    )

    # Notions fragiles : exclut les nœuds verrouillés, inutile d'envoyer
    # quelqu'un sur une notion dont les prérequis ne sont pas acquis.
    weak = [
        n
        for n in nodes
        if n.mastery < MASTERED_THRESHOLD and n.status != NodeStatus.locked.value
    ][:5]

    return SubjectDetail(
        **summary.model_dump(),
        nodes=[NodeRead.model_validate(n) for n in nodes],
        weak_nodes=[NodeRead.model_validate(n) for n in weak],
        documents=[DocumentRead.model_validate(d) for d in documents],
        advice=_advice(summary, weak),
    )


def _advice(summary: SubjectSummary, weak: list[KnowledgeNode]) -> str:
    """Une phrase qui dit par où commencer, à partir des chiffres réels."""
    if summary.cards_due:
        return (
            f"{summary.cards_due} carte{'s' if summary.cards_due > 1 else ''} "
            "à réviser maintenant : commence par là, l'oubli n'attend pas."
        )
    if summary.nodes_critical:
        return (
            f"{summary.nodes_critical} notion{'s' if summary.nodes_critical > 1 else ''} "
            "en régression. Reprends-les avant d'ouvrir un nouveau front."
        )
    if weak:
        return (
            f"Attaque « {weak[0].title} » : c'est ta notion la plus fragile "
            f"({weak[0].mastery:.0%} de maîtrise)."
        )
    if not summary.documents_total:
        return (
            "Aucun cours importé dans cette matière. Ajoute un document pour "
            "que l'application puisse générer des cartes et répondre à tes questions."
        )
    return "Tout est à jour dans cette matière. Profites-en pour prendre de l'avance."
