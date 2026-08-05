"""
Socle commun des modèles SQLAlchemy.

`Base` est la classe mère : Alembic l'inspecte pour détecter les changements
de schéma et générer les migrations automatiquement.

Note sur les énumérations : elles sont stockées en `VARCHAR`, pas en type ENUM
PostgreSQL. Ajouter une valeur à un ENUM natif demande du SQL manuel dans une
migration ; avec du texte + validation Pydantic, une nouvelle valeur ne coûte
rien. Compromis assumé pour un projet qui va beaucoup bouger.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Conventions de nommage explicites : sans elles, PostgreSQL invente les noms
# de contraintes et Alembic ne sait plus les retrouver pour les supprimer.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Ajoute created_at / updated_at gérés par PostgreSQL lui-même."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
