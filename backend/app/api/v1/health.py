"""
Endpoints de santé et de diagnostic.

`/health` ne touche pas la base : c'est lui que sonde le HEALTHCHECK Docker.
S'il dépendait de PostgreSQL, un simple hoquet de la base ferait redémarrer
le conteneur applicatif en boucle — alors que l'API va parfaitement bien.

`/health/detailed` teste chaque dépendance, à utiliser pour diagnostiquer.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.core.config import settings
from app.core.deps import DbSession
from app.schemas.ai import AiStatusRead
from app.services.ai.openrouter import get_ai_client
from app.services.rag.embeddings import get_embedder
from app.services.rag.qdrant import get_vector_store

router = APIRouter(tags=["système"])


@router.get("/health", summary="Sonde de vivacité")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": __version__,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/detailed", summary="État de chaque dépendance")
async def health_detailed(db: DbSession) -> dict[str, object]:
    checks: dict[str, object] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as exc:
        checks["postgres"] = {"status": "error", "detail": str(exc)[:200]}

    reachable = await get_vector_store().health()
    checks["qdrant"] = {"status": "ok" if reachable else "unreachable"}

    client = get_ai_client()
    checks["ai"] = {
        "status": "mock" if client.is_mocked else "live",
        "models": {
            "cheap": settings.AI_MODEL_CHEAP,
            "standard": settings.AI_MODEL_STANDARD,
            "reasoning": settings.AI_MODEL_REASONING,
        },
    }

    degraded = any(
        isinstance(v, dict) and v.get("status") in {"error", "unreachable"}
        for v in checks.values()
    )
    return {"status": "degraded" if degraded else "ok", "checks": checks}


@router.get("/ai/status", response_model=AiStatusRead, summary="Configuration IA")
async def ai_status() -> AiStatusRead:
    """Ce que fait l'IA en ce moment — affiché dans l'écran de réglages."""
    client = get_ai_client()
    embedder = get_embedder()

    if settings.AI_MOCK:
        reason = "AI_MOCK=true : réponses simulées, aucun appel réseau."
    elif not settings.OPENROUTER_API_KEY:
        reason = "OPENROUTER_API_KEY absente : repli automatique sur le mode simulé."
    else:
        reason = "Modèles réels via OpenRouter."

    return AiStatusRead(
        mocked=client.is_mocked,
        reason=reason,
        models={
            "cheap": settings.AI_MODEL_CHEAP,
            "standard": settings.AI_MODEL_STANDARD,
            "reasoning": settings.AI_MODEL_REASONING,
        },
        embedder=embedder.name,
        embedding_dim=embedder.dim,
        qdrant_reachable=await get_vector_store().health(),
    )
