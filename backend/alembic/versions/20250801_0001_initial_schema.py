"""Schéma initial — création de toutes les tables.

Revision ID: 0001
Revises: None

Cette première migration délègue à `Base.metadata.create_all` : le schéma créé
est exactement celui que déclarent les modèles, sans risque de divergence entre
un DDL recopié à la main et le code. C'est un choix assumé pour la migration
zéro d'un projet neuf.

À partir d'ici, la règle change : chaque évolution des modèles passe par

    docker compose exec backend alembic revision --autogenerate -m "description"
    docker compose exec backend alembic upgrade head

Alembic comparera les modèles à la base et écrira le fichier de migration —
qu'on RELIT avant de l'appliquer : l'autogénération rate parfois les
renommages (elle voit un drop + add).
"""

from __future__ import annotations

from alembic import op

from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
