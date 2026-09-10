"""create api_usage table

Revision ID: 0167762f70c6
Revises: 23c25a82537f
Create Date: 2026-09-08 01:00:41.825349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0167762f70c6'
down_revision: Union[str, Sequence[str], None] = '23c25a82537f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'api_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('month', sa.DateTime(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'month', name='uq_api_usage_user_month')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('api_usage')