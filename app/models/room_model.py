from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.booking_model import Bookings


class Rooms(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column()
    price: Mapped[int] = mapped_column(nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    amenities: Mapped[str | None] = mapped_column()
    quantity: Mapped[int] = mapped_column(nullable=False)
    location: Mapped[str] = mapped_column(nullable=False)

    bookings: Mapped[list["Bookings"]] = relationship("Bookings", back_populates="room", cascade="all, delete")