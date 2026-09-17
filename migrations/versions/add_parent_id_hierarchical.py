"""add parent_id to url_registry and agencies for hierarchical structure

Revision ID: add_parent_id_hierarchical
Revises: competitive_analysis_v1
Create Date: 2026-09-13 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_parent_id_hierarchical"
down_revision: Union[str, Sequence[str], None] = "competitive_analysis_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("agencies", "url_registry"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(f"fk_{table}_parent_id", table, ["parent_id"], ["id"])
            batch.create_index(f"ix_{table}_parent_id", ["parent_id"], unique=False)


def downgrade() -> None:
    for table in ("url_registry", "agencies"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_parent_id")
            batch.drop_constraint(f"fk_{table}_parent_id", type_="foreignkey")
            batch.drop_column("parent_id")
