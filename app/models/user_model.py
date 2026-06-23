import re
from typing import TYPE_CHECKING
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.database import Base
from app.models.role_model import Role

if TYPE_CHECKING:
    from app.models.booking_model import Bookings


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[Role] = mapped_column(nullable=False, server_default="user")

    bookings: Mapped[list["Bookings"]] = relationship("Bookings", back_populates="user")

    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        return email.lower()

    @validates('username')
    def validate_username(self, key, username):
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return username