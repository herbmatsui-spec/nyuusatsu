"""add_allowed_prefectures_to_users

Revision ID: add_allowed_prefectures_to_users
Revises: 202609131530
Create Date: 2026-09-13 15:41:46.410261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_allowed_prefectures_to_users'
down_revision: Union[str, Sequence[str], None] = '202609131530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('allowed_prefectures', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'allowed_prefectures')
