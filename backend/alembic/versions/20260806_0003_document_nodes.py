"""Association documents ↔ notions du graphe.

Revision ID: 0003
Revises: 0002

Un document couvre plusieurs notions et une notion apparaît dans plusieurs
documents — une fiche de révision BTS SIO touche les onze matières à elle
seule. Une colonne `node_id` sur `documents` serait donc structurellement
fausse : il faut une table d'association.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_nodes",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_nodes_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["knowledge_nodes.id"],
            name=op.f("fk_document_nodes_node_id_knowledge_nodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "document_id", "node_id", name=op.f("pk_document_nodes")
        ),
    )
    # Index sur node_id : la clé primaire couvre déjà (document_id, node_id),
    # mais pas la recherche inverse « quels documents parlent de cette notion ».
    op.create_index(
        op.f("ix_document_nodes_node_id"), "document_nodes", ["node_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_nodes_node_id"), table_name="document_nodes")
    op.drop_table("document_nodes")
