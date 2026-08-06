"""
Flashcards et révision.

`POST /cards/{id}/review` est l'endpoint le plus important de l'application :
c'est lui qui reçoit chaque auto-évaluation, replanifie la carte, met à jour la
maîtrise du nœud correspondant, alimente le streak et — en cas d'échec —
renvoie le diagnostic des prérequis fautifs.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.content import Document, DocumentChunk
from app.models.enums import Subject
from app.models.graph import KnowledgeNode
from app.models.learning import Card
from app.schemas.graph import NodeRead
from app.schemas.learning import (
    CardCreate,
    CardQueueItem,
    CardRead,
    CardUpdate,
    GenerateCardsRequest,
    GenerateCardsResponse,
    QuizQuestion,
    QuizRequest,
    QuizResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.services.ai import service as ai_service
from app.services.ai.openrouter import get_ai_client
from app.services.srs import service as srs_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cards", tags=["flashcards"])

# Limite du texte envoyé à l'IA pour générer des cartes. Au-delà, le modèle
# survole et produit des cartes génériques : mieux vaut plusieurs passes ciblées.
MAX_SOURCE_CHARS = 8000
# En dessous, il n'y a pas de quoi construire une question honnête.
MIN_SOURCE_CHARS = 120


async def _get_owned_card(db, user, card_id: int) -> Card:
    card = await db.get(Card, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Carte introuvable."
        )
    return card


async def _check_node(db, user, node_id: int | None) -> None:
    if node_id is None:
        return
    node = await db.get(KnowledgeNode, node_id)
    if node is None or node.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Notion introuvable."
        )


# ═════════════════════════════════════════════════════════════════════════
#  File de révision
# ═════════════════════════════════════════════════════════════════════════
@router.get(
    "/queue",
    response_model=list[CardQueueItem],
    summary="Cartes à réviser maintenant",
)
async def read_queue(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    subject: Subject | None = None,
    node_id: int | None = Query(
        default=None, description="Cibler une seule notion (mode Focus)."
    ),
    interleave: bool = Query(
        default=True,
        description="Alterner les matières (recommandé : meilleure rétention).",
    ),
) -> list[CardQueueItem]:
    cards = await srs_service.get_due_queue(
        db,
        user.id,
        limit=limit,
        subject=subject.value if subject else None,
        node_id=node_id,
        interleave=interleave,
    )
    return [
        CardQueueItem(
            **CardRead.model_validate(card).model_dump(),
            node_title=card.node.title if card.node else None,
            node_subject=card.node.subject if card.node else None,
        )
        for card in cards
    ]


@router.post(
    "/generate",
    response_model=GenerateCardsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer des cartes par IA",
)
async def generate_cards(
    payload: GenerateCardsRequest, user: CurrentUser, db: DbSession
) -> GenerateCardsResponse:
    """
    Génère des flashcards depuis un document importé ou un texte collé.

    Les cartes sont créées immédiatement en base. C'est un choix : les faire
    valider une par une avant insertion casse l'élan. Elles sont marquées
    `ai_generated`, donc filtrables et supprimables en masse si la fournée
    est mauvaise.
    """
    await _check_node(db, user, payload.node_id)

    source_text = payload.text.strip()
    document: Document | None = None
    subject = Subject.other.value

    if payload.document_id:
        document = await db.get(Document, payload.document_id)
        if document is None or document.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable."
            )
        subject = document.subject
        chunks = (
            await db.execute(
                select(DocumentChunk.content)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.ordinal)
            )
        ).scalars().all()
        source_text = "\n\n".join(chunks)[:MAX_SOURCE_CHARS]

    if not source_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fournis un `document_id` ou un `text` non vide.",
        )

    # Rattachement automatique à la notion du document.
    #
    # Sans ça, les cartes générées depuis un cours flottaient sans nœud : les
    # réviser ne faisait progresser aucune maîtrise, et le graphe restait figé
    # alors que l'utilisateur travaillait. Un trou silencieux, donc le pire.
    #
    # On ne devine QUE si le document est rattaché à une seule notion. À
    # plusieurs, l'association serait arbitraire — mieux vaut laisser vide et
    # que l'utilisateur range lui-même.
    node_id = payload.node_id
    if node_id is None and document is not None and len(document.nodes) == 1:
        node_id = document.nodes[0].id
        logger.info(
            "Cartes rattachées automatiquement à la notion %s (document %s)",
            node_id,
            document.id,
        )

    drafts = await ai_service.generate_flashcards(
        source_text, count=payload.count, subject=subject
    )
    if not drafts:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'IA n'a produit aucune carte exploitable. Réessaie.",
        )

    created: list[Card] = []
    for draft in drafts:
        card = Card(
            user_id=user.id,
            node_id=node_id,
            document_id=document.id if document else None,
            kind=draft.kind,
            front=draft.front,
            back=draft.back,
            hint=draft.hint,
            explanation=draft.explanation,
            ai_generated=True,
        )
        db.add(card)
        created.append(card)

    await srs_service.touch_activity(db, user, cards_created=len(created))
    await db.commit()
    for card in created:
        await db.refresh(card)

    mocked = get_ai_client().is_mocked
    return GenerateCardsResponse(
        created=len(created),
        cards=[CardRead.model_validate(c) for c in created],
        model="mock" if mocked else "openrouter",
        mocked=mocked,
    )


async def _source_text(
    db, user, *, document_id: int | None, node_id: int | None, fallback: str
) -> tuple[str, str]:
    """
    Rassemble le texte de travail et son étiquette d'origine.

    Trois sources possibles, dans l'ordre de précision : un document précis,
    une notion (on prend alors ses cartes existantes), ou du texte collé.
    """
    if document_id:
        document = await db.get(Document, document_id)
        if document is None or document.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable."
            )
        chunks = (
            await db.execute(
                select(DocumentChunk.content)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.ordinal)
            )
        ).scalars().all()
        return "\n\n".join(chunks)[:MAX_SOURCE_CHARS], document.title

    if node_id:
        node = await db.get(KnowledgeNode, node_id)
        if node is None or node.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notion introuvable."
            )
        rows = (
            await db.execute(
                select(Card.front, Card.back)
                .where(Card.user_id == user.id, Card.node_id == node.id)
                .limit(40)
            )
        ).all()
        material = "\n".join(f"{front} → {back}" for front, back in rows)
        body = f"{node.description}\n{material}".strip()
        # Une notion sans description ni cartes ne contient rien à interroger :
        # générer quand même produirait des questions sur le seul titre, ce qui
        # décrédibilise la fonctionnalité entière.
        if len(body) < MIN_SOURCE_CHARS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"« {node.title} » n'a pas encore de contenu exploitable. "
                    "Importe un cours sur cette notion ou génère-lui des cartes "
                    "avant de lancer un quiz."
                ),
            )
        return f"{node.title}\n{body}"[:MAX_SOURCE_CHARS], node.title

    return fallback.strip()[:MAX_SOURCE_CHARS], "texte libre"


@router.post("/quiz", response_model=QuizResponse, summary="Générer un quiz")
async def generate_quiz(
    payload: QuizRequest, user: CurrentUser, db: DbSession
) -> QuizResponse:
    """
    Quiz de vérification, généré à la demande et **non persisté**.

    C'est délibéré : un quiz est un contrôle ponctuel. Le conserver
    reviendrait à réviser les mêmes questions par cœur, ce qui teste la
    mémoire des questions et non la compréhension. Ce qui doit durer, ce sont
    les cartes SRS — elles, sont en base.
    """
    source_text, label = await _source_text(
        db,
        user,
        document_id=payload.document_id,
        node_id=payload.node_id,
        fallback=payload.text,
    )
    if not source_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fournis un document, une notion, ou un texte.",
        )

    questions = await ai_service.generate_quiz(source_text, count=payload.count)
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'IA n'a produit aucune question exploitable. Réessaie.",
        )

    mocked = get_ai_client().is_mocked
    return QuizResponse(
        questions=[QuizQuestion(**q) for q in questions],
        source=label,
        model="mock" if mocked else "openrouter",
        mocked=mocked,
    )


# ═════════════════════════════════════════════════════════════════════════
#  CRUD
# ═════════════════════════════════════════════════════════════════════════
@router.get("", response_model=list[CardRead], summary="Lister mes cartes")
async def list_cards(
    user: CurrentUser,
    db: DbSession,
    node_id: int | None = None,
    document_id: int | None = None,
    ai_generated: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CardRead]:
    stmt = select(Card).where(Card.user_id == user.id)
    if node_id is not None:
        stmt = stmt.where(Card.node_id == node_id)
    if document_id is not None:
        stmt = stmt.where(Card.document_id == document_id)
    if ai_generated is not None:
        stmt = stmt.where(Card.ai_generated.is_(ai_generated))

    rows = await db.execute(
        stmt.order_by(Card.due_at.asc()).limit(limit).offset(offset)
    )
    return [CardRead.model_validate(c) for c in rows.scalars().all()]


@router.post(
    "",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une carte",
)
async def create_card(
    payload: CardCreate, user: CurrentUser, db: DbSession
) -> CardRead:
    await _check_node(db, user, payload.node_id)

    card = Card(
        user_id=user.id,
        node_id=payload.node_id,
        document_id=payload.document_id,
        kind=payload.kind.value,
        front=payload.front.strip(),
        back=payload.back.strip(),
        hint=payload.hint.strip(),
        explanation=payload.explanation.strip(),
    )
    db.add(card)
    await srs_service.touch_activity(db, user, cards_created=1)
    await db.commit()
    await db.refresh(card)
    return CardRead.model_validate(card)


@router.get("/{card_id}", response_model=CardRead, summary="Détail d'une carte")
async def read_card(card_id: int, user: CurrentUser, db: DbSession) -> CardRead:
    return CardRead.model_validate(await _get_owned_card(db, user, card_id))


@router.patch("/{card_id}", response_model=CardRead, summary="Modifier une carte")
async def update_card(
    card_id: int, payload: CardUpdate, user: CurrentUser, db: DbSession
) -> CardRead:
    card = await _get_owned_card(db, user, card_id)
    data = payload.model_dump(exclude_unset=True)
    if "node_id" in data:
        await _check_node(db, user, data["node_id"])
    for field_name, value in data.items():
        if value is not None or field_name == "node_id":
            setattr(card, field_name, value)
    await db.commit()
    await db.refresh(card)
    return CardRead.model_validate(card)


@router.delete(
    "/{card_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une carte"
)
async def delete_card(card_id: int, user: CurrentUser, db: DbSession) -> None:
    card = await _get_owned_card(db, user, card_id)
    await db.delete(card)
    await db.commit()


# ═════════════════════════════════════════════════════════════════════════
#  Révision
# ═════════════════════════════════════════════════════════════════════════
@router.post(
    "/{card_id}/review",
    response_model=ReviewResponse,
    summary="Répondre à une carte",
)
async def review_card(
    card_id: int, payload: ReviewRequest, user: CurrentUser, db: DbSession
) -> ReviewResponse:
    card = await _get_owned_card(db, user, card_id)

    card, weak = await srs_service.review(
        db, user, card, payload.rating, duration_ms=payload.duration_ms
    )
    await db.commit()
    await db.refresh(card)

    diagnosis = ""
    if weak:
        worst = weak[0]
        diagnosis = (
            f"Piste : « {worst.title} » n'est qu'à {worst.mastery:.0%} de maîtrise. "
            "C'est probablement là que se situe le vrai blocage."
        )

    return ReviewResponse(
        card=CardRead.model_validate(card),
        next_due_at=card.due_at,
        interval_days=card.interval_days,
        weak_prerequisites=[NodeRead.model_validate(n) for n in weak],
        diagnosis=diagnosis,
        remaining_due=await srs_service.count_due(db, user.id),
    )
