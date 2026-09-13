"""Add indexes on agencies.category_id and agencies.priority_level for filtering performance.

Revision ID: add_agency_filter_indexes
Revises: ecbedd8292b7
Create Date: 2026-09-12 19:42:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_agency_filter_indexes'
down_revision: Union[str, Sequence[str], None] = 'ecbedd8292b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes to improve BaseCrawler._get_target_agencies filtering performance."""
    op.create_index('ix_agencies_category_id', 'agencies', ['category_id'])
    op.create_index('ix_agencies_priority_level', 'agencies', ['priority_level'])


def downgrade() -> None:
    """Drop the filtering indexes."""
    op.drop_index('ix_agencies_priority_level', table_name='agencies')
    op.drop_index('ix_agencies_category_id', table_name='agencies')
