"""add billing columns to users

Revision ID: 23c25a82537f
Revises: add_backfill_job_tables
Create Date: 2026-09-08 00:23:44.413822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23c25a82537f'
down_revision: Union[str, Sequence[str], None] = 'add_backfill_job_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns first
    op.add_column('users', sa.Column('plan', sa.String(length=20), server_default='free', nullable=False))
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('stripe_subscription_id', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('subscription_status', sa.String(length=20), server_default='inactive', nullable=False))
    op.add_column('users', sa.Column('current_period_end', sa.DateTime(), nullable=True))
    # Note: Unique constraints skipped for SQLite compatibility
    # Enforced at application layer via model/index


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'current_period_end')
    op.drop_column('users', 'subscription_status')
    op.drop_column('users', 'trial_ends_at')
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_column('users', 'plan')