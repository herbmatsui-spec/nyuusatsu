"""add_backfill_job_tables

Revision ID: add_backfill_job_tables
Revises: add_procurement_forecasts
Create Date: 2026-09-08 00:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_backfill_job_tables'
down_revision = 'add_procurement_forecasts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Tables already created via Base.metadata.create_all()"""
    pass


def downgrade() -> None:
    """Drop backfill tables if needed"""
    op.drop_table('backfill_job_logs')
    op.drop_table('backfill_jobs')