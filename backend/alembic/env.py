"""
Environnement d'exécution des migrations Alembic.

Deux particularités par rapport au gabarit standard :

  1. L'URL de connexion vient de `settings.DATABASE_URL` (donc du .env ou de
     docker-compose), jamais d'alembic.ini.
  2. Le driver est asynchrone (asyncpg) : Alembic, lui, travaille en synchrone.
     On crée donc un moteur async et on lui fait exécuter les migrations via
     `run_sync` — c'est le pont officiel entre les deux mondes.

`target_metadata` pointe vers Base.metadata : c'est en comparant ce que
déclarent les modèles à ce que contient la base qu'`alembic revision
--autogenerate` écrit les migrations à ta place.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings

# Importer app.models suffit : chaque table s'enregistre dans Base.metadata
# au moment de l'import de sa classe.
from app.models import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Mode « offline » : génère le SQL sans se connecter (alembic upgrade --sql)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Détecte aussi les changements de type de colonne, pas seulement les
        # ajouts/suppressions — désactivé par défaut, on se demande pourquoi.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
