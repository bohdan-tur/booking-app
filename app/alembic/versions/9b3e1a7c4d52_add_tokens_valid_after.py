"""add tokens valid after

Revision ID: 9b3e1a7c4d52
Revises: 6d4f7c8a91b2
Create Date: 2026-07-30 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b3e1a7c4d52"
down_revision: str | Sequence[str] | None = "6d4f7c8a91b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tokens_valid_after", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "tokens_valid_after")
