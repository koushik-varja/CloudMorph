"""create portfolios table"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("app_count", sa.Float(), nullable=False),
    )
    op.create_index("ix_portfolios_name", "portfolios", ["name"])


def downgrade() -> None:
    op.drop_index("ix_portfolios_name", table_name="portfolios")
    op.drop_table("portfolios")
