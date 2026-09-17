from alembic import op
import sqlalchemy as sa


revision = "unified_search_bid_type"
down_revision = "add_parent_id_hierarchical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bids", sa.Column("bid_type", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("bids", "bid_type")
