"""Quality alert table migration.

Revision ID: quality_alert
Revises: add_backfill_job_tables
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa


revision = 'quality_alert'
down_revision = 'add_backfill_job_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'quality_alert',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric', sa.String(length=100), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_quality_alert_metric', 'quality_alert', ['metric'])
    op.create_index('ix_quality_alert_sent_at', 'quality_alert', ['sent_at'])


def downgrade() -> None:
    op.drop_index('ix_quality_alert_sent_at', table_name='quality_alert')
    op.drop_index('ix_quality_alert_metric', table_name='quality_alert')
    op.drop_table('quality_alert')
