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
from app.core.utils import slugify
from app.models.content import Document, DocumentChunk
from app.models.enums import DocumentCollection, Subject
from app.models.graph import KnowledgeNode
from app.schemas.content import (
    ApplyMappingRequest,
    ApplyMappingResponse,
    ChunkRead,
    DocumentMappingRead,
    DocumentRead,
    DocumentUpdate,
    IngestResponse,
    NodeProposal,
    SearchHitRead,
    SearchRequest,
    SearchResponse,
)
from app.services.ai import service as ai_service
from app.services.graph import engine as graph_engine
from app.services.graph.matcher import extract_candidates, match_title
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


# Mots-clés qui trahissent la matière d'une notion. Volontairement simple et
# gratuit : deviner « algèbre de Boole → maths » ne justifie pas un appel de
# modèle facturé. L'utilisateur corrige d'un clic si le verdict est faux.
SUBJECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    Subject.sql.value: ("sql", "requet", "jointure", "table", "base de donn", "merise", "mcd"),
    Subject.dev.value: ("php", "symfony", "poo", "objet", "class", "algorithm", "python",
                        "javascript", "api", "mvc", "doctrine", "git", "test unitaire"),
    Subject.network.value: ("reseau", "ip", "tcp", "osi", "dns", "dhcp", "vlan",
                            "routage", "linux", "serveur", "cloud", "virtualisation"),
    Subject.security.value: ("securit", "cyber", "rgpd", "chiffr", "authentif",
                             "injection", "xss", "jwt", "https", "vulnerab", "sauvegarde"),
    Subject.math.value: ("math", "boole", "graphe", "probabilit", "suite", "matrice",
                         "arithmetique", "logique", "ordonnancement", "statistique"),
    Subject.cejm.value: ("juridique", "droit", "contrat", "entreprise", "economi",
                         "management", "marche", "concurrence", "strateg", "salarie"),
    Subject.cge.value: ("synthese", "argument", "expression", "culture generale",
                        "redaction", "dissertation", "ecriture personnelle"),
    Subject.english.value: ("anglais", "english", "verbe irregulier", "vocabulary",
                            "grammar", "toeic"),
}


def _guess_subject(title: str, fallback: str) -> str:
    """Devine la matière d'une notion d'après son intitulé."""
    normalised = slugify(title).replace("-", " ")
    for subject, keywords in SUBJECT_KEYWORDS.items():
        if any(keyword in normalised for keyword in keywords):
            return subject
    return fallback


@router.get(
    "/{document_id}/map",
    response_model=DocumentMappingRead,
    summary="Quelles notions ce document couvre-t-il ?",
)
async def map_document(
    document_id: int, user: CurrentUser, db: DbSession
) -> DocumentMappingRead:
    """
    Rapproche les sections du document des notions déjà présentes au graphe.

    C'est la réponse au problème du doublon : sans ce rapprochement, importer
    trois fiches contenant « Algèbre de Boole » créerait trois notions
    distinctes, chacune avec sa propre maîtrise, et le graphe perdrait tout
    sens.

    Rien n'est écrit ici : l'endpoint PROPOSE. Les cas certains sont
    pré-cochés, les cas douteux attendent une décision. Un graphe faux est
    pire qu'un graphe incomplet — il oriente les révisions vers de mauvaises
    notions.
    """
    document = await _get_owned_document(db, user, document_id)

    headings = (
        await db.execute(
            select(DocumentChunk.heading)
            .where(DocumentChunk.document_id == document.id, DocumentChunk.heading != "")
            .order_by(DocumentChunk.ordinal)
        )
    ).scalars().all()

    candidates = extract_candidates(list(headings))
    if not candidates:
        return DocumentMappingRead(
            document_id=document.id,
            document_title=document.title,
            headings_found=0,
            message=(
                "Aucun titre de section exploitable. Le document est probablement "
                "un PDF sans structure : le rattachement doit se faire à la main."
            ),
        )

    nodes = (
        await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.user_id == user.id)
        )
    ).scalars().all()
    linked = {n.id for n in document.nodes}

    proposals = []
    for candidate in candidates:
        match = match_title(candidate.title, list(nodes))
        proposals.append(
            NodeProposal(
                title=candidate.title,
                verdict=match.verdict,
                score=match.score,
                matched_node_id=match.node.id if match.node else None,
                matched_node_title=match.node.title if match.node else "",
                matched_node_subject=match.node.subject if match.node else "",
                # Deviné sur le fil d'Ariane complet : « Les sept couches du
                # modèle » ne dit rien, « Modèle OSI > Les sept couches » dit
                # « réseau ».
                suggested_subject=_guess_subject(
                    candidate.breadcrumb, document.subject
                ),
                # Les rapprochements certains sont pré-cochés ; le reste non.
                selected=match.verdict == "certain",
            )
        )

    certain = sum(1 for p in proposals if p.verdict == "certain")
    new = sum(1 for p in proposals if p.verdict == "new")
    return DocumentMappingRead(
        document_id=document.id,
        document_title=document.title,
        headings_found=len(candidates),
        proposals=proposals,
        already_linked=sorted(linked),
        message=(
            f"{len(candidates)} notions détectées : {certain} déjà au graphe, "
            f"{new} inconnues, {len(proposals) - certain - new} à confirmer."
        ),
    )


@router.post(
    "/{document_id}/map",
    response_model=ApplyMappingResponse,
    summary="Rattacher le document aux notions choisies",
)
async def apply_mapping(
    document_id: int,
    payload: ApplyMappingRequest,
    user: CurrentUser,
    db: DbSession,
) -> ApplyMappingResponse:
    document = await _get_owned_document(db, user, document_id)

    existing = (
        await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.user_id == user.id)
        )
    ).scalars().all()
    by_slug = {n.slug: n for n in existing}
    linked_ids = {n.id for n in document.nodes}

    created = 0
    linked = 0

    for decision in payload.decisions:
        node: KnowledgeNode | None = None

        if decision.node_id is not None:
            node = await db.get(KnowledgeNode, decision.node_id)
            if node is None or node.user_id != user.id:
                continue
        elif decision.create:
            slug = slugify(decision.title)
            # Ceinture et bretelles : même après le rapprochement, deux titres
            # différents peuvent produire le même slug. La contrainte d'unicité
            # en base lèverait une erreur ; on réutilise plutôt le nœud.
            node = by_slug.get(slug)
            if node is None:
                node = KnowledgeNode(
                    user_id=user.id,
                    slug=slug,
                    title=decision.title.strip()[:200],
                    subject=decision.subject.value,
                    description=f"Notion issue de « {document.title} ».",
                )
                db.add(node)
                await db.flush()
                by_slug[slug] = node
                created += 1

        if node is not None and node.id not in linked_ids:
            document.nodes.append(node)
            linked_ids.add(node.id)
            linked += 1

    if created:
        await graph_engine.recompute_locks(db, user.id)
    await db.commit()

    logger.info(
        "Document %s rattaché : %s notions créées, %s liens",
        document.id, created, linked,
    )
    return ApplyMappingResponse(
        created=created,
        linked=linked,
        document_id=document.id,
        message=(
            f"{linked} notion(s) rattachée(s) au document, dont {created} "
            "nouvelle(s) au graphe."
        ),
    )


@router.get("/limits/upload", summary="Contraintes d'import")
async def upload_limits() -> dict[str, object]:
    """Consommé par le frontend pour valider côté client avant l'envoi."""
    return {
        "max_mb": settings.MAX_UPLOAD_MB,
        "extensions": sorted(SUPPORTED_EXTENSIONS),
        "collections": [c.value for c in DocumentCollection],
        "subjects": [s.value for s in Subject],
    }
