from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.booking_status import BookingStatus

if TYPE_CHECKING:
    from app.models.room_model import Rooms
    from app.models.user_model import Users


class Bookings(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_bookings_valid_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(
            BookingStatus,
            name="booking_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=BookingStatus.ACTIVE,
        server_default=text("'ACTIVE'"),
    )

    room: Mapped["Rooms"] = relationship("Rooms", back_populates="bookings")
    user: Mapped["Users"] = relationship("Users", back_populates="bookings")
