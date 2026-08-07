"""
Pipeline d'ingestion — le cœur de la valeur de REVISIO.

    fichier → extraction → découpage → embeddings → Qdrant + PostgreSQL

Séquencement voulu : tout ce qui peut échouer (format illisible, PDF scanné,
doublon) est vérifié AVANT la première écriture en base. On évite ainsi les
documents fantômes bloqués en statut « processing » qu'il faut nettoyer à la
main — la panne classique de ce genre de pipeline.

Le fichier original est conservé sur disque. Quand un meilleur extracteur
arrivera (OCR, parser PDF plus fin), on pourra tout ré-ingérer sans avoir à
redemander les fichiers.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.content import Document, DocumentChunk
from app.models.enums import DocumentCollection, DocumentStatus, Subject
from app.models.user import User
from app.services.rag.embeddings import get_embedder
from app.services.rag.extractors import extract_text
from app.services.rag.qdrant import SearchHit, VectorPoint, get_vector_store
from app.services.rag.splitter import split_text

logger = logging.getLogger(__name__)


class DuplicateDocument(ValueError):
    """Ce contenu exact a déjà été importé."""

    def __init__(self, existing: Document) -> None:
        super().__init__(f"Document déjà importé : « {existing.title} ».")
        self.existing = existing


class DocumentTooLarge(ValueError):
    pass


@dataclass(slots=True)
class IngestResult:
    document: Document
    chunk_count: int
    vectors_indexed: int
    warning: str = ""


# ═════════════════════════════════════════════════════════════════════════
#  Ingestion
# ═════════════════════════════════════════════════════════════════════════
async def ingest(
    db: AsyncSession,
    user: User,
    *,
    data: bytes,
    filename: str,
    mime_type: str = "",
    collection: str = DocumentCollection.course.value,
    subject: str = Subject.other.value,
    title: str | None = None,
) -> IngestResult:
    if len(data) > settings.max_upload_bytes:
        raise DocumentTooLarge(
            f"Fichier trop volumineux ({len(data) / 1_048_576:.1f} Mo). "
            f"Limite : {settings.MAX_UPLOAD_MB} Mo."
        )

    content_hash = hashlib.sha256(data).hexdigest()

    existing = (
        await db.execute(
            select(Document).where(
                Document.user_id == user.id, Document.content_hash == content_hash
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise DuplicateDocument(existing)

    # ── Extraction + découpage : avant toute écriture ────────────────────
    extracted = extract_text(data, filename)
    chunks = split_text(
        extracted.text,
        max_chars=settings.CHUNK_MAX_CHARS,
        overlap_chars=settings.CHUNK_OVERLAP_CHARS,
    )
    if not chunks:
        raise ValueError("Aucun contenu exploitable après découpage.")

    storage_path = _persist_file(data, user.id, content_hash, filename)

    document = Document(
        user_id=user.id,
        title=(title or extracted.detected_title or Path(filename).stem)[:300],
        original_filename=filename[:300],
        mime_type=mime_type[:120],
        size_bytes=len(data),
        content_hash=content_hash,
        storage_path=storage_path,
        collection=collection,
        subject=subject,
        status=DocumentStatus.processing.value,
        char_count=len(extracted.text),
        chunk_count=len(chunks),
    )
    db.add(document)
    # flush et non commit : on veut l'id auto-généré tout en gardant la
    # possibilité d'annuler l'ensemble si la suite échoue.
    await db.flush()

    embedder = get_embedder()
    vectors = await embedder.embed_documents([c.content for c in chunks])

    points: list[VectorPoint] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        point_id = str(uuid.uuid4())
        db.add(
            DocumentChunk(
                document_id=document.id,
                user_id=user.id,
                ordinal=chunk.ordinal,
                content=chunk.content,
                char_count=chunk.char_count,
                heading=chunk.heading[:300],
                point_id=point_id,
            )
        )
        points.append(
            VectorPoint(
                point_id=point_id,
                vector=vector,
                payload={
                    "user_id": user.id,
                    "document_id": document.id,
                    "document_title": document.title,
                    "collection": collection,
                    "subject": subject,
                    "ordinal": chunk.ordinal,
                    "heading": chunk.heading,
                    # Le texte est dupliqué dans le payload : ça évite un
                    # aller-retour en base pour afficher un résultat.
                    "text": chunk.content,
                },
            )
        )

    warning = ""
    indexed = 0
    try:
        indexed = await get_vector_store().upsert(
            collection, points, dim=embedder.dim
        )
        document.status = DocumentStatus.ready.value
    except Exception as exc:
        # Les chunks restent en PostgreSQL : `reindex` pourra rattraper sans
        # relire le fichier d'origine.
        logger.error("Indexation Qdrant échouée pour le doc %s : %s", document.id, exc)
        document.status = DocumentStatus.failed.value
        document.error_message = (
            "Texte extrait et enregistré, mais l'indexation vectorielle a "
            "échoué. Vérifie que Qdrant tourne, puis relance la ré-indexation."
        )
        warning = document.error_message

    return IngestResult(
        document=document,
        chunk_count=len(chunks),
        vectors_indexed=indexed,
        warning=warning,
    )


def _persist_file(data: bytes, user_id: int, content_hash: str, filename: str) -> str:
    """
    Écrit le fichier sous `storage/<user>/<2 premiers car. du hash>/<hash><ext>`.

    Le sous-dossier à 2 caractères évite d'accumuler des dizaines de milliers
    de fichiers dans un seul répertoire — ce que la plupart des systèmes de
    fichiers gèrent très mal.
    """
    suffix = Path(filename).suffix.lower()[:16]
    relative = Path(str(user_id)) / content_hash[:2] / f"{content_hash}{suffix}"
    absolute = settings.STORAGE_DIR / relative
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(data)
    return relative.as_posix()


# ═════════════════════════════════════════════════════════════════════════
#  Recherche
# ═════════════════════════════════════════════════════════════════════════
async def search(
    user: User,
    query: str,
    *,
    collections: list[str] | None = None,
    top_k: int | None = None,
    subject: str | None = None,
    document_ids: list[int] | None = None,
) -> list[SearchHit]:
    """
    Recherche sémantique dans les documents de l'utilisateur.

    `document_ids` restreint le périmètre aux seuls documents rattachés à la
    notion travaillée : c'est la dernière brique du référentiel. Sans elle,
    une question sur l'algèbre de Boole peut remonter du CEJM parce que deux
    formulations se ressemblent.
    """
    query = (query or "").strip()
    if not query:
        return []

    embedder = get_embedder()
    vector = await embedder.embed_query(query)

    return await get_vector_store().search(
        vector=vector,
        user_id=user.id,
        collections=collections or [c.value for c in DocumentCollection],
        # `or` et non `if is None` : un top_k à 0 n'aurait aucun sens, la
        # valeur configurée reprend la main.
        top_k=top_k or settings.RAG_TOP_K,
        subject=subject,
        document_ids=document_ids,
        dim=embedder.dim,
    )


def build_context(hits: list[SearchHit], *, max_chars: int = 6000) -> str:
    """
    Assemble les extraits trouvés en un bloc de contexte destiné au prompt.

    Chaque extrait est numéroté et sourcé pour que l'IA puisse écrire
    « d'après [2] » — et que tu puisses vérifier. Une IA qui cite ses sources
    est une IA qu'on peut prendre en défaut, donc en qui on peut avoir
    confiance.
    """
    blocks: list[str] = []
    used = 0
    for index, hit in enumerate(hits, start=1):
        source = hit.document_title or "document"
        if hit.heading:
            source += f" — {hit.heading}"
        block = f"[{index}] ({source})\n{hit.text}"
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n---\n\n".join(blocks)


# ═════════════════════════════════════════════════════════════════════════
#  Maintenance
# ═════════════════════════════════════════════════════════════════════════
async def reindex(db: AsyncSession, user: User, document: Document) -> int:
    """Re-vectorise un document depuis les chunks stockés en PostgreSQL."""
    chunks = (
        await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.ordinal)
        )
    ).scalars().all()
    if not chunks:
        return 0

    embedder = get_embedder()
    vectors = await embedder.embed_documents([c.content for c in chunks])

    points = [
        VectorPoint(
            point_id=chunk.point_id or str(uuid.uuid4()),
            vector=vector,
            payload={
                "user_id": user.id,
                "document_id": document.id,
                "document_title": document.title,
                "collection": document.collection,
                "subject": document.subject,
                "ordinal": chunk.ordinal,
                "heading": chunk.heading,
                "text": chunk.content,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    for chunk, point in zip(chunks, points, strict=True):
        chunk.point_id = point.point_id

    indexed = await get_vector_store().upsert(
        document.collection, points, dim=embedder.dim
    )
    document.status = DocumentStatus.ready.value
    document.error_message = ""
    return indexed


async def purge_document(db: AsyncSession, document: Document) -> None:
    """Supprime vecteurs, fichier et lignes. Irréversible."""
    await get_vector_store().delete_document(document.collection, document.id)

    if document.storage_path:
        target = settings.STORAGE_DIR / document.storage_path
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Fichier non supprimé (%s) : %s", target, exc)

    # Les chunks partent en cascade (ondelete=CASCADE côté modèle).
    await db.delete(document)
