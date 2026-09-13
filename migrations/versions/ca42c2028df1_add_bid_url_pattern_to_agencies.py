"""add bid_url_pattern to agencies

Revision ID: ca42c2028df1
Revises: add_agency_filter_indexes
Create Date: 2026-09-13 11:31:12.354149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca42c2028df1'
down_revision: Union[str, Sequence[str], None] = 'add_agency_filter_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('agencies', sa.Column('bid_url_pattern', sa.VARCHAR(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('agencies', 'bid_url_pattern')
