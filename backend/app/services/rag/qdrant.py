"""
Accès à Qdrant — la mémoire sémantique de REVISIO.

ORGANISATION : une collection Qdrant par type de contenu, préfixée par le nom
de l'app → `revisio_course`, `revisio_exam`, `revisio_error`, `revisio_note`.

Pourquoi séparer plutôt que tout mettre ensemble ? Parce que les intentions de
recherche sont différentes et qu'on veut pouvoir les cibler :
  • « explique-moi les jointures »   → cherche dans `course`
  • « ça tombe souvent au BTS ? »    → cherche dans `exam`
  • « je refais souvent cette faute ? » → cherche dans `error`
Filtrer par payload marcherait aussi, mais des collections distinctes restent
plus lisibles et se sauvegardent/purgent indépendamment.

ISOLATION : chaque point porte `user_id` dans son payload et toute recherche
est filtrée dessus. Un index de payload est créé sur ce champ, sans quoi le
filtrage devient un scan complet dès quelques milliers de points.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VectorPoint:
    point_id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchHit:
    point_id: str
    score: float
    payload: dict[str, Any]

    @property
    def text(self) -> str:
        return str(self.payload.get("text", ""))

    @property
    def heading(self) -> str:
        return str(self.payload.get("heading", ""))

    @property
    def document_title(self) -> str:
        return str(self.payload.get("document_title", ""))


class VectorStore:
    def __init__(self) -> None:
        self._client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=30,
        )
        self._ready: set[str] = set()

    @staticmethod
    def collection_name(collection: str) -> str:
        return f"{settings.QDRANT_COLLECTION_PREFIX}_{collection}"

    async def health(self) -> bool:
        try:
            await self._client.get_collections()
            return True
        except Exception as exc:
            logger.warning("Qdrant injoignable : %s", exc)
            return False

    async def ensure_collection(self, collection: str, dim: int) -> str:
        """
        Crée la collection si besoin. Idempotent, et mémoïsé en mémoire pour ne
        pas interroger Qdrant à chaque insertion de chunk.
        """
        name = self.collection_name(collection)
        if name in self._ready:
            return name

        if not await self._client.collection_exists(name):
            logger.info("Création de la collection Qdrant %s (dim=%s)", name, dim)
            await self._client.create_collection(
                collection_name=name,
                # COSINE : on compare des directions, pas des longueurs. C'est
                # la métrique attendue par les modèles d'embeddings modernes.
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            for payload_field in ("user_id", "document_id", "subject"):
                try:
                    await self._client.create_payload_index(
                        collection_name=name,
                        field_name=payload_field,
                        field_schema=(
                            PayloadSchemaType.INTEGER
                            if payload_field.endswith("_id")
                            else PayloadSchemaType.KEYWORD
                        ),
                    )
                except Exception as exc:
                    logger.debug("Index %s déjà présent ou refusé : %s", payload_field, exc)

        self._ready.add(name)
        return name

    async def upsert(
        self, collection: str, points: list[VectorPoint], *, dim: int
    ) -> int:
        if not points:
            return 0
        name = await self.ensure_collection(collection, dim)
        await self._client.upsert(
            collection_name=name,
            points=[
                PointStruct(id=p.point_id, vector=p.vector, payload=p.payload)
                for p in points
            ],
            wait=True,
        )
        return len(points)

    async def search(
        self,
        *,
        vector: list[float],
        user_id: int,
        collections: list[str],
        top_k: int = 6,
        subject: str | None = None,
        document_ids: list[int] | None = None,
        dim: int | None = None,
    ) -> list[SearchHit]:
        """
        Recherche dans plusieurs collections et fusionne les résultats.

        Qdrant ne sait pas chercher dans plusieurs collections d'un coup : on
        interroge chacune puis on trie sur le score global.
        """
        conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ]
        if subject:
            conditions.append(
                FieldCondition(key="subject", match=MatchValue(value=subject))
            )
        if document_ids:
            # Périmètre imposé : on ne cherche que dans les documents rattachés
            # à la notion travaillée. C'est ce qui évite qu'une question sur
            # l'algèbre de Boole remonte du CEJM parce que deux mots se
            # ressemblent — moins de bruit, contexte plus court, réponse plus
            # juste.
            conditions.append(
                FieldCondition(
                    key="document_id", match=MatchAny(any=list(document_ids))
                )
            )
        query_filter = Filter(must=conditions)

        hits: list[SearchHit] = []
        for collection in collections:
            name = self.collection_name(collection)
            try:
                if not await self._client.collection_exists(name):
                    continue
                response = await self._client.query_points(
                    collection_name=name,
                    query=vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )
                hits.extend(
                    SearchHit(
                        point_id=str(p.id),
                        score=float(p.score),
                        payload=dict(p.payload or {}),
                    )
                    for p in response.points
                )
            except Exception as exc:
                logger.warning("Recherche impossible dans %s : %s", name, exc)

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    async def delete_document(self, collection: str, document_id: int) -> None:
        name = self.collection_name(collection)
        try:
            if not await self._client.collection_exists(name):
                return
            await self._client.delete(
                collection_name=name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id", match=MatchValue(value=document_id)
                        )
                    ]
                ),
                wait=True,
            )
        except Exception as exc:
            logger.warning("Suppression Qdrant échouée (doc %s) : %s", document_id, exc)

    async def close(self) -> None:
        await self._client.close()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return VectorStore()
