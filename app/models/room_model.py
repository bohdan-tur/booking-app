from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.booking_model import Bookings


class Rooms(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_rooms_positive_price"),
        CheckConstraint("capacity BETWEEN 1 AND 10", name="ck_rooms_valid_capacity"),
        CheckConstraint("total_units >= 0", name="ck_rooms_non_negative_total_units"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column()
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    amenities: Mapped[str | None] = mapped_column()
    total_units: Mapped[int] = mapped_column(nullable=False)
    location: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    bookings: Mapped[list["Bookings"]] = relationship("Bookings", back_populates="room")
