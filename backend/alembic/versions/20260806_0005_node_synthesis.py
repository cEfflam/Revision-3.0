"""Synthèse consolidée par notion.

Revision ID: 0005
Revises: 0004

Le RAG rassemble aujourd'hui quatre à six fragments épars à chaque question.
Ils se recoupent, se contredisent parfois, et coûtent plus de jetons qu'un
texte unique et ordonné.

Cette colonne stocke une note de synthèse par notion, fusionnant tout ce qui
lui a été rattaché. Elle devient le contexte PRINCIPAL ; les fragments bruts
restent en appui pour le détail exact — une synthèse est lossy, elle perdra
l'article de loi précis ou la syntaxe exacte.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_nodes",
        sa.Column("synthesis", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "knowledge_nodes",
        sa.Column("synthesis_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_nodes",
        sa.Column(
            "synthesis_source_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_nodes", "synthesis_source_count")
    op.drop_column("knowledge_nodes", "synthesis_updated_at")
    op.drop_column("knowledge_nodes", "synthesis")
