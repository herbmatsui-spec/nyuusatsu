"""Update saved_search user_id to Integer FK

Revision ID: 202609131530
Revises: ca42c2028df1
Create Date: 2026-09-13 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202609131530'
down_revision = 'ca42c2028df1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    # Since SQLite doesn't support altering column type, we recreate the table
    # Note: table is empty, so we can drop and create
    op.drop_table('saved_searches')
    op.create_table(
        'saved_searches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('criteria_json', sa.Text(), nullable=False),
        sa.Column('last_notified_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text("'1'")),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text("'CURRENT_TIMESTAMP'")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text("'CURRENT_TIMESTAMP'")),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    # Create indexes if needed (none specified)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('saved_searches')
    op.create_table(
        'saved_searches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('criteria_json', sa.Text(), nullable=False),
        sa.Column('last_notified_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text("'1'")),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )