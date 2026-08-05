"""
Vectorisation du texte (embeddings).

Un embedding transforme un texte en liste de nombres où la proximité
géométrique traduit la proximité de sens. « clé étrangère » et « FOREIGN KEY »
finissent voisins alors qu'ils ne partagent aucun caractère : c'est
exactement ce qu'une recherche par mots-clés est incapable de faire.

Trois fournisseurs, choisis par la variable EMBEDDING_PROVIDER :

  fastembed  Local, gratuit, aucune clé API. Le modèle (~130 Mo) est téléchargé
             au premier appel puis mis en cache. Défaut recommandé.
  openai     Payant, très bonne qualité, dépend du réseau.
  hash       Repli déterministe sans aucune dépendance. Sémantiquement pauvre
             (sac de mots), mais permet de faire tourner et tester tout le
             pipeline hors ligne.

Modèle par défaut : `intfloat/multilingual-e5-small`. Multilingue, ce qui n'est
pas un détail — tes cours sont en français et la moitié des modèles « small »
populaires sont entraînés sur l'anglais seul.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

# Les modèles de la famille E5 attendent un préfixe explicite indiquant le rôle
# du texte. Sans lui, la qualité chute nettement — c'est documenté par les
# auteurs et systématiquement oublié.
E5_DOCUMENT_PREFIX = "passage: "
E5_QUERY_PREFIX = "query: "


class Embedder(ABC):
    """Contrat commun. Tout le reste du code ne connaît que cette interface."""

    name: str = "abstract"
    dim: int = 0

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...


# ═════════════════════════════════════════════════════════════════════════
#  fastembed — local
# ═════════════════════════════════════════════════════════════════════════
class FastEmbedEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        logger.info("Chargement du modèle d'embeddings %s…", model_name)
        self._model = TextEmbedding(
            model_name=model_name, cache_dir=".fastembed_cache"
        )
        self.name = f"fastembed:{model_name}"
        self._is_e5 = "e5" in model_name.lower()

        # On mesure la dimension réelle au lieu de faire confiance au .env :
        # une dimension fausse fait échouer l'insertion dans Qdrant avec un
        # message très peu parlant.
        probe = next(iter(self._model.embed(["dimension probe"])))
        self.dim = len(probe)
        if self.dim != settings.EMBEDDING_DIM:
            logger.warning(
                "EMBEDDING_DIM=%s dans la config mais le modèle produit %s "
                "dimensions. C'est la valeur du modèle qui est utilisée.",
                settings.EMBEDDING_DIM,
                self.dim,
            )

    def _encode(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = [E5_DOCUMENT_PREFIX + t for t in texts] if self._is_e5 else texts
        # fastembed est synchrone et gourmand en CPU : sans `to_thread`, il
        # bloquerait la boucle asyncio et l'API entière figerait pendant
        # l'indexation d'un gros PDF.
        return await asyncio.to_thread(self._encode, payload)

    async def embed_query(self, text: str) -> list[float]:
        payload = E5_QUERY_PREFIX + text if self._is_e5 else text
        vectors = await asyncio.to_thread(self._encode, [payload])
        return vectors[0]


# ═════════════════════════════════════════════════════════════════════════
#  OpenAI — API distante
# ═════════════════════════════════════════════════════════════════════════
class OpenAIEmbedder(Embedder):
    def __init__(self, model_name: str, api_key: str) -> None:
        self._model = model_name
        self._api_key = api_key
        self.name = f"openai:{model_name}"
        self.dim = settings.EMBEDDING_DIM

    async def _call(self, inputs: list[str]) -> list[list[float]]:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "input": inputs},
            )
            response.raise_for_status()
            data = response.json()["data"]
        # L'API ne garantit pas l'ordre : on retrie sur l'index.
        return [item["embedding"] for item in sorted(data, key=lambda d: d["index"])]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._call(texts) if texts else []

    async def embed_query(self, text: str) -> list[float]:
        return (await self._call([text]))[0]


# ═════════════════════════════════════════════════════════════════════════
#  hash — repli hors ligne
# ═════════════════════════════════════════════════════════════════════════
class HashEmbedder(Embedder):
    """
    Sac de mots projeté par hachage. Aucun apprentissage, donc aucune vraie
    sémantique : deux textes ne se ressemblent que s'ils partagent des mots.
    Suffisant pour valider la plomberie du pipeline sans réseau.
    """

    _TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.name = "hash"

    def _encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in self._TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dim
            # Signe dérivé du hash : évite que tous les vecteurs pointent dans
            # le même octant, ce qui écraserait toutes les similarités.
            vector[index] += 1.0 if digest[0] % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._encode(text)


# ═════════════════════════════════════════════════════════════════════════
#  Fabrique
# ═════════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """
    Instancie le fournisseur configuré, une seule fois pour tout le process.

    En cas d'échec (modèle non téléchargeable, clé absente), on retombe sur
    `HashEmbedder` avec un avertissement explicite plutôt que de faire tomber
    l'API : mieux vaut une recherche dégradée qu'un backend mort.
    """
    provider = settings.EMBEDDING_PROVIDER.lower().strip()

    if provider == "fastembed":
        try:
            return FastEmbedEmbedder(settings.EMBEDDING_MODEL)
        except Exception as exc:
            logger.error(
                "fastembed indisponible (%s) → repli sur l'embedder 'hash'. "
                "La recherche sémantique sera approximative.",
                exc,
            )
            return HashEmbedder(settings.EMBEDDING_DIM)

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            logger.error(
                "EMBEDDING_PROVIDER=openai mais OPENAI_API_KEY est vide "
                "→ repli sur l'embedder 'hash'."
            )
            return HashEmbedder(settings.EMBEDDING_DIM)
        return OpenAIEmbedder(settings.EMBEDDING_MODEL, settings.OPENAI_API_KEY)

    return HashEmbedder(settings.EMBEDDING_DIM)
