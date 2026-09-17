"""Add competitive analysis columns to bids table.

Adds:
  - specification_text: LLM-extracted specification text
  - specification_text_clean: preprocessed specification text for similarity
  - bid_difficulty_score: 0-100 difficulty score
  - win_prediction_score: 0-1 win prediction probability

Revision ID: competitive_analysis_v1
Revises: add_allowed_prefectures_to_users
Create Date: 2026-09-13 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'competitive_analysis_v1'
down_revision: Union[str, Sequence[str], None] = 'b7aff60ba7d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add competitive analysis columns to bids table."""
    op.add_column('bids', sa.Column('specification_text', sa.Text(), nullable=True))
    op.add_column('bids', sa.Column('specification_text_clean', sa.Text(), nullable=True))
    op.add_column('bids', sa.Column('bid_difficulty_score', sa.Float(), nullable=True))
    op.add_column('bids', sa.Column('win_prediction_score', sa.Float(), nullable=True))

    # Indexes for faster lookups on scored columns
    op.create_index('ix_bids_bid_difficulty_score', 'bids', ['bid_difficulty_score'])
    op.create_index('ix_bids_win_prediction_score', 'bids', ['win_prediction_score'])
    op.create_index('ix_bids_specification_text_clean', 'bids', ['specification_text_clean'])


def downgrade() -> None:
    """Remove competitive analysis columns from bids table."""
    op.drop_index('ix_bids_specification_text_clean', table_name='bids')
    op.drop_index('ix_bids_win_prediction_score', table_name='bids')
    op.drop_index('ix_bids_bid_difficulty_score', table_name='bids')
    op.drop_column('bids', 'win_prediction_score')
    op.drop_column('bids', 'bid_difficulty_score')
    op.drop_column('bids', 'specification_text_clean')
    op.drop_column('bids', 'specification_text')
