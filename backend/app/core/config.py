"""
Configuration centrale de l'application.

Principe : *aucune* valeur de configuration n'est écrite en dur dans le code.
Tout passe par des variables d'environnement, lues et validées une seule fois
ici par Pydantic. Si une variable est manquante ou mal typée, l'application
refuse de démarrer avec un message clair — plutôt que de planter trois heures
plus tard sur un `None` inattendu.

Usage partout ailleurs :
    from app.core.config import settings
    settings.DATABASE_URL
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # En local (hors Docker), on lit le .env de la racine du monorepo.
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Identité & environnement ─────────────────────────────────────────
    APP_NAME: str = "REVISIO"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ── Sécurité ─────────────────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 jours
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Base de données ──────────────────────────────────────────────────
    # Valeur par défaut = accès depuis l'hôte Windows (port 5433).
    # docker-compose écrase cette variable pour viser le service `postgres`.
    DATABASE_URL: str = (
        "postgresql+asyncpg://revisio:revisio_dev_password@localhost:5433/revisio"
    )
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # ── Compte de démonstration (dev) ────────────────────────────────────
    SEED_DEMO_USER: bool = False
    # Pas de domaine .local/.test ici : le validateur EmailStr de Pydantic
    # rejette les noms réservés, la connexion serait impossible.
    DEMO_USER_EMAIL: str = "demo@revisio.app"
    DEMO_USER_PASSWORD: str = "revisio123"

    # ── Qdrant ───────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_PREFIX: str = "revisio"

    # ── IA / OpenRouter ──────────────────────────────────────────────────
    AI_MOCK: bool = True
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_APP_NAME: str = "REVISIO"
    OPENROUTER_SITE_URL: str = "http://localhost:3000"
    AI_MODEL_CHEAP: str = "deepseek/deepseek-v4-flash-0731"
    AI_MODEL_STANDARD: str = "deepseek/deepseek-v4-flash-0731"
    AI_MODEL_REASONING: str = "deepseek/deepseek-v4-flash-0731"
    AI_REQUEST_TIMEOUT: int = 120
    # Interrupteur général du raisonnement. Même à true, il n'est activé que
    # sur les tâches du palier « reasoning » (voir services/ai/router.py).
    # Le passer à false coupe TOUS les jetons de réflexion — utile en fin de
    # mois si le budget est serré.
    AI_REASONING: bool = True

    # ── Embeddings ───────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "fastembed"  # fastembed | openai | hash
    # Doit figurer dans TextEmbedding.list_supported_models() de fastembed.
    # Multilingue obligatoire : les cours sont en français.
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384
    OPENAI_API_KEY: str | None = None

    # ── RAG ──────────────────────────────────────────────────────────────
    CHUNK_MAX_CHARS: int = 1200
    CHUNK_OVERLAP_CHARS: int = 150
    RAG_TOP_K: int = 6
    MAX_UPLOAD_MB: int = 25
    STORAGE_DIR: Path = BACKEND_DIR / "storage"

    # ── Propriétés dérivées ──────────────────────────────────────────────
    @property
    def cors_origins(self) -> list[str]:
        """
        CORS_ORIGINS est une chaîne séparée par des virgules et non une vraie
        liste : Pydantic tenterait de parser du JSON sur un champ `list[str]`,
        ce qui échoue sur `a,b`. On découpe donc à la main.
        """
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Instance unique, mise en cache : le .env n'est lu qu'une fois."""
    return Settings()


settings = get_settings()
