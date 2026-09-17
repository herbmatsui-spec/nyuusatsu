"""add_llm_extracted_fields_to_bid

Revision ID: b7aff60ba7d6
Revises: add_allowed_prefectures_to_users
Create Date: 2026-09-13 15:43:05.898869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7aff60ba7d6'
down_revision: Union[str, Sequence[str], None] = 'add_allowed_prefectures_to_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bids', sa.Column('delivery_deadline', sa.Date(), nullable=True))
    op.create_index('ix_bids_delivery_deadline', 'bids', ['delivery_deadline'])
    op.create_index('ix_bids_budget_amount', 'bids', ['budget_amount'])
    op.create_index('ix_bids_qualifications', 'bids', ['qualifications'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_bids_qualifications', table_name='bids')
    op.drop_index('ix_bids_budget_amount', table_name='bids')
    op.drop_index('ix_bids_delivery_deadline', table_name='bids')
    op.drop_column('bids', 'delivery_deadline')
