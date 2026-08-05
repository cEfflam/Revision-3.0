"""
Le « Brain » — import de documents et recherche sémantique.

L'import est synchrone : la requête HTTP ne rend la main qu'une fois le document
extrait, découpé, vectorisé et indexé. C'est assumé pour un usage mono-
utilisateur — un PDF de cours prend quelques secondes et l'utilisateur voit
immédiatement le résultat. Le jour où ça devient gênant (gros corpus, plusieurs
fichiers d'un coup), l'étape lourde passera dans une file de tâches
(ARQ/Celery) sans changer le contrat de l'API.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models.content import Document, DocumentChunk
from app.models.enums import DocumentCollection, Subject
from app.schemas.content import (
    ChunkRead,
    DocumentRead,
    DocumentUpdate,
    IngestResponse,
    SearchHitRead,
    SearchRequest,
    SearchResponse,
)
from app.services.ai import service as ai_service
from app.services.rag import pipeline
from app.services.rag.embeddings import get_embedder
from app.services.rag.extractors import SUPPORTED_EXTENSIONS, UnsupportedDocument
from app.services.rag.pipeline import DocumentTooLarge, DuplicateDocument
from app.services.rag.qdrant import get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


async def _get_owned_document(db, user, document_id: int) -> Document:
    document = await db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable."
        )
    return document


# ═════════════════════════════════════════════════════════════════════════
#  Import
# ═════════════════════════════════════════════════════════════════════════
@router.post(
    "/upload",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importer un document (PDF, DOCX, Markdown, TXT)",
)
async def upload_document(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    collection: DocumentCollection = Form(default=DocumentCollection.course),
    subject: Subject = Form(default=Subject.other),
    title: str | None = Form(default=None),
    generate_summary: bool = Form(
        default=True, description="Produire le résumé exécutif à l'import."
    ),
) -> IngestResponse:
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide."
        )

    try:
        result = await pipeline.ingest(
            db,
            user,
            data=data,
            filename=file.filename or "document",
            mime_type=file.content_type or "",
            collection=collection.value,
            subject=subject.value,
            title=title,
        )
    except DuplicateDocument as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DocumentTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except UnsupportedDocument as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if generate_summary:
        # Un résumé raté ne doit pas faire échouer un import réussi : le
        # document et ses vecteurs sont déjà en place, c'est l'essentiel.
        try:
            chunks = (
                await db.execute(
                    select(DocumentChunk.content)
                    .where(DocumentChunk.document_id == result.document.id)
                    .order_by(DocumentChunk.ordinal)
                    .limit(12)
                )
            ).scalars().all()
            result.document.summary = await ai_service.generate_summary(
                "\n\n".join(chunks)
            )
        except Exception as exc:
            logger.warning("Résumé non généré pour le doc %s : %s", result.document.id, exc)

    await db.commit()
    await db.refresh(result.document)

    return IngestResponse(
        document=DocumentRead.model_validate(result.document),
        chunk_count=result.chunk_count,
        vectors_indexed=result.vectors_indexed,
        warning=result.warning,
    )


# ═════════════════════════════════════════════════════════════════════════
#  Recherche sémantique
# ═════════════════════════════════════════════════════════════════════════
@router.post(
    "/search", response_model=SearchResponse, summary="Recherche sémantique"
)
async def search_documents(
    payload: SearchRequest, user: CurrentUser
) -> SearchResponse:
    hits = await pipeline.search(
        user,
        payload.query,
        collections=[c.value for c in payload.collections] or None,
        top_k=payload.top_k,
        subject=payload.subject.value if payload.subject else None,
    )
    return SearchResponse(
        query=payload.query,
        hits=[
            SearchHitRead(
                document_title=hit.document_title,
                heading=hit.heading,
                excerpt=hit.text[:600],
                score=round(hit.score, 4),
                document_id=hit.payload.get("document_id"),
                ordinal=hit.payload.get("ordinal"),
            )
            for hit in hits
        ],
        embedder=get_embedder().name,
    )


# ═════════════════════════════════════════════════════════════════════════
#  Bibliothèque
# ═════════════════════════════════════════════════════════════════════════
@router.get("", response_model=list[DocumentRead], summary="Ma bibliothèque")
async def list_documents(
    user: CurrentUser,
    db: DbSession,
    collection: DocumentCollection | None = None,
    subject: Subject | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[DocumentRead]:
    stmt = select(Document).where(Document.user_id == user.id)
    if collection:
        stmt = stmt.where(Document.collection == collection.value)
    if subject:
        stmt = stmt.where(Document.subject == subject.value)

    rows = await db.execute(
        stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    )
    return [DocumentRead.model_validate(d) for d in rows.scalars().all()]


@router.get("/{document_id}", response_model=DocumentRead, summary="Détail")
async def read_document(
    document_id: int, user: CurrentUser, db: DbSession
) -> DocumentRead:
    return DocumentRead.model_validate(
        await _get_owned_document(db, user, document_id)
    )


@router.get(
    "/{document_id}/chunks",
    response_model=list[ChunkRead],
    summary="Fragments indexés",
)
async def read_chunks(
    document_id: int,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ChunkRead]:
    """Utile pour vérifier de tes yeux que le découpage est propre."""
    document = await _get_owned_document(db, user, document_id)
    rows = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.ordinal)
        .limit(limit)
    )
    return [ChunkRead.model_validate(c) for c in rows.scalars().all()]


@router.patch("/{document_id}", response_model=DocumentRead, summary="Reclasser")
async def update_document(
    document_id: int, payload: DocumentUpdate, user: CurrentUser, db: DbSession
) -> DocumentRead:
    document = await _get_owned_document(db, user, document_id)
    data = payload.model_dump(exclude_unset=True)

    previous_collection = document.collection
    for field_name, value in data.items():
        if value is not None:
            setattr(
                document,
                field_name,
                value.value if hasattr(value, "value") else value,
            )

    # Changer de collection = changer de collection Qdrant : il faut retirer les
    # anciens vecteurs et réindexer, sinon le document devient invisible.
    if document.collection != previous_collection:
        await get_vector_store().delete_document(previous_collection, document.id)
        await pipeline.reindex(db, user, document)

    await db.commit()
    await db.refresh(document)
    return DocumentRead.model_validate(document)


@router.post(
    "/{document_id}/reindex", response_model=DocumentRead, summary="Ré-indexer"
)
async def reindex_document(
    document_id: int, user: CurrentUser, db: DbSession
) -> DocumentRead:
    """
    Re-vectorise depuis les fragments stockés en PostgreSQL. À utiliser après
    une panne de Qdrant ou un changement de modèle d'embeddings.
    """
    document = await _get_owned_document(db, user, document_id)
    indexed = await pipeline.reindex(db, user, document)
    await db.commit()
    await db.refresh(document)
    logger.info("Document %s ré-indexé (%s vecteurs)", document.id, indexed)
    return DocumentRead.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer définitivement",
)
async def delete_document(
    document_id: int, user: CurrentUser, db: DbSession
) -> None:
    """Supprime le fichier, les fragments et les vecteurs. Irréversible."""
    document = await _get_owned_document(db, user, document_id)
    await pipeline.purge_document(db, document)
    await db.commit()


@router.get("/limits/upload", summary="Contraintes d'import")
async def upload_limits() -> dict[str, object]:
    """Consommé par le frontend pour valider côté client avant l'envoi."""
    return {
        "max_mb": settings.MAX_UPLOAD_MB,
        "extensions": sorted(SUPPORTED_EXTENSIONS),
        "collections": [c.value for c in DocumentCollection],
        "subjects": [s.value for s in Subject],
    }
