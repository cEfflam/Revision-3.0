"""Table des étapes de parcours (roadmap générée par l'IA).

Revision ID: 0002
Revises: 0001

Première migration incrémentale du projet — écrite à la main plutôt que
générée, parce qu'une seule table est ajoutée et que le SQL reste lisible.
Pour les évolutions futures, préférer :

    alembic revision --autogenerate -m "description"

…puis RELIRE le fichier produit : l'autogénération voit un renommage de
colonne comme une suppression suivie d'un ajout, ce qui détruit les données.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roadmap_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("node_id", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column(
            "estimated_minutes",
            sa.Integer(),
            server_default=sa.text("60"),
            nullable=False,
        ),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("prerequisites", sa.Text(), nullable=False),
        sa.Column(
            "is_done", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_roadmap_steps_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_roadmap_steps_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["knowledge_nodes.id"],
            name=op.f("fk_roadmap_steps_node_id_knowledge_nodes"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roadmap_steps")),
    )
    op.create_index(
        op.f("ix_roadmap_steps_user_id"), "roadmap_steps", ["user_id"], unique=False
    )
    op.create_index(
        "ix_roadmap_user_order", "roadmap_steps", ["user_id", "order_index"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_roadmap_user_order", table_name="roadmap_steps")
    op.drop_index(op.f("ix_roadmap_steps_user_id"), table_name="roadmap_steps")
    op.drop_table("roadmap_steps")
