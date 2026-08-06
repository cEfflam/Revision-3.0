"""Hiérarchie de contenance des notions (Matière > Thème > Notion).

Revision ID: 0004
Revises: 0003

Pourquoi une colonne `parent_id` alors qu'il existe déjà des arêtes ?

Parce que les deux relations répondent à des questions différentes et se
croisent. `parent_id` dit « où cette notion se range-t-elle dans mon
référentiel » ; une arête `prerequisite` dit « que faut-il maîtriser avant ».
Doctrine ORM se range sous Symfony mais a pour prérequis une notion de SQL,
dans une branche entièrement différente. Les confondre rendrait l'un des deux
usages impossible.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_nodes", sa.Column("parent_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "knowledge_nodes",
        sa.Column(
            "position", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.create_foreign_key(
        op.f("fk_knowledge_nodes_parent_id_knowledge_nodes"),
        "knowledge_nodes",
        "knowledge_nodes",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Index sur (user_id, parent_id) : l'affichage de l'arbre demande les
    # enfants d'un nœud, jamais un parcours global.
    op.create_index(
        "ix_node_user_parent", "knowledge_nodes", ["user_id", "parent_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_node_user_parent", table_name="knowledge_nodes")
    op.drop_constraint(
        op.f("fk_knowledge_nodes_parent_id_knowledge_nodes"),
        "knowledge_nodes",
        type_="foreignkey",
    )
    op.drop_column("knowledge_nodes", "position")
    op.drop_column("knowledge_nodes", "parent_id")
