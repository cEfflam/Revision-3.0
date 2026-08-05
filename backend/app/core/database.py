"""
Connexion PostgreSQL en asynchrone (SQLAlchemy 2.0).

Deux objets seulement comptent ici :
  • `engine`        : le pool de connexions, créé une fois pour tout le process.
  • `SessionLocal`  : une usine à sessions ; on en ouvre une par requête HTTP.

Règle : une requête HTTP = une session = une transaction. Le `commit` est
toujours explicite dans l'endpoint, jamais caché dans une dépendance — comme
ça, en lisant un endpoint, tu sais exactement quand la donnée est écrite.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    # Teste la connexion avant de la prêter : évite les "server closed the
    # connection unexpectedly" quand PostgreSQL a redémarré entre-temps.
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # False : après un commit, les objets restent lisibles. Sans ça, tout
    # accès à un attribut déclencherait un rechargement… hors session. Erreur
    # classique et pénible à diagnostiquer.
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI : injecte une session, la referme toujours."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
