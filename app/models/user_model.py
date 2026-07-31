import re
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.database import Base
from app.models.role_model import Role

if TYPE_CHECKING:
    from app.models.booking_model import Booking
    from app.models.refresh_token_model import RefreshToken

MIN_USERNAME_LENGTH = 3


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    tokens_valid_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    role: Mapped[Role] = mapped_column(nullable=False, server_default="user")

    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("username")
    def validate_username(self, key: str, username: str) -> str:
        if len(username) < MIN_USERNAME_LENGTH:
            raise ValueError(
                f"Username must be at least {MIN_USERNAME_LENGTH} characters long"
            )
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores"
            )
        return username
