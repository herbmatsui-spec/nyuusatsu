"""merge_heads

Revision ID: ecbedd8292b7
Revises: 0167762f70c6, quality_alert
Create Date: 2026-09-12 19:28:10.815929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecbedd8292b7'
down_revision: Union[str, Sequence[str], None] = ('0167762f70c6', 'quality_alert')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
