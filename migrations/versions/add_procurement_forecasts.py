"""Add procurement_forecasts table

Revision ID: add_procurement_forecasts
Revises:
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_procurement_forecasts'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'procurement_forecasts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agency_id', sa.Integer(), sa.ForeignKey('agencies.id'), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('quarter', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('estimated_budget', sa.String(length=255), nullable=True),
        sa.Column('estimated_budget_amount', sa.Integer(), nullable=True),
        sa.Column('expected_publish_date', sa.DateTime(), nullable=True),
        sa.Column('expected_bid_date', sa.DateTime(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('industry_category', sa.String(length=100), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('pdf_url', sa.String(length=1024), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('priority_level', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('related_bid_id', sa.Integer(), sa.ForeignKey('bids.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_crawled_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_procurement_forecasts_agency_id', 'procurement_forecasts', ['agency_id'])
    op.create_index('ix_procurement_forecasts_category', 'procurement_forecasts', ['category'])
    op.create_index('ix_procurement_forecasts_industry_category', 'procurement_forecasts', ['industry_category'])
    op.create_index('ix_procurement_forecasts_status', 'procurement_forecasts', ['status'])

    op.add_column('crawl_logs', sa.Column('crawl_type', sa.String(length=50), nullable=True))

    op.create_table(
        'customer_forecast_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('forecast_id', sa.Integer(), sa.ForeignKey('procurement_forecasts.id'), nullable=False),
        sa.Column('linked_at', sa.DateTime(), nullable=True),
        sa.Column('interest_level', sa.String(length=20), nullable=True),
        sa.Column('memo', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'forecast_alert_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('min_budget_amount', sa.Integer(), nullable=True),
        sa.Column('keyword', sa.String(length=255), nullable=True),
        sa.Column('agency_id', sa.Integer(), sa.ForeignKey('agencies.id'), nullable=True),
        sa.Column('is_active', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'forecast_statuses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('forecast_id', sa.Integer(), sa.ForeignKey('procurement_forecasts.id'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.Column('changed_by', sa.String(length=100), nullable=True),
        sa.Column('memo', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('forecast_statuses')
    op.drop_table('procurement_forecasts')