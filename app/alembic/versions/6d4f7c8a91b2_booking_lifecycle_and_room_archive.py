"""booking lifecycle and room archive

Revision ID: 6d4f7c8a91b2
Revises: a29a1c0a9c73
Create Date: 2026-07-30 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6d4f7c8a91b2"
down_revision: str | Sequence[str] | None = "a29a1c0a9c73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("rooms", "quantity", new_column_name="total_units")
    op.alter_column(
        "rooms",
        "price",
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
        postgresql_using="price::numeric(10, 2)",
    )
    op.add_column(
        "rooms",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_rooms_non_negative_total_units", "rooms", "total_units >= 0"
    )
    op.create_check_constraint("ck_rooms_positive_price", "rooms", "price > 0")
    op.create_check_constraint(
        "ck_rooms_valid_capacity", "rooms", "capacity BETWEEN 1 AND 10"
    )

    op.drop_constraint("bookings_room_id_fkey", "bookings", type_="foreignkey")
    op.create_foreign_key(
        "bookings_room_id_fkey",
        "bookings",
        "rooms",
        ["room_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        UPDATE bookings
        SET status = CASE lower(status)
            WHEN 'active' THEN 'ACTIVE'
            WHEN 'cancelled' THEN 'CANCELLED'
            WHEN 'completed' THEN 'COMPLETED'
            WHEN 'expired' THEN 'COMPLETED'
            ELSE 'COMPLETED'
        END
        """
    )
    op.alter_column(
        "bookings",
        "status",
        existing_type=sa.String(),
        server_default=sa.text("'ACTIVE'"),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "booking_status",
        "bookings",
        "status IN ('ACTIVE', 'CANCELLED', 'COMPLETED')",
    )

    op.alter_column(
        "bookings",
        "start_time",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="start_time AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "bookings",
        "end_time",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="end_time AT TIME ZONE 'UTC'",
    )
    op.create_check_constraint(
        "ck_bookings_valid_period", "bookings", "start_time < end_time"
    )


def downgrade() -> None:
    op.drop_constraint("ck_bookings_valid_period", "bookings", type_="check")
    op.alter_column(
        "bookings",
        "end_time",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="end_time AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "bookings",
        "start_time",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="start_time AT TIME ZONE 'UTC'",
    )

    op.drop_constraint("booking_status", "bookings", type_="check")
    op.execute("UPDATE bookings SET status = lower(status)")
    op.alter_column(
        "bookings",
        "status",
        existing_type=sa.String(),
        server_default=None,
        existing_nullable=False,
    )

    op.drop_constraint("bookings_room_id_fkey", "bookings", type_="foreignkey")
    op.create_foreign_key(
        "bookings_room_id_fkey",
        "bookings",
        "rooms",
        ["room_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("ck_rooms_valid_capacity", "rooms", type_="check")
    op.drop_constraint("ck_rooms_positive_price", "rooms", type_="check")
    op.drop_constraint("ck_rooms_non_negative_total_units", "rooms", type_="check")
    op.drop_column("rooms", "is_active")
    op.alter_column(
        "rooms",
        "price",
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="price::integer",
    )
    op.alter_column("rooms", "total_units", new_column_name="quantity")
