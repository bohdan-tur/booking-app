from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking_model import Booking
from app.models.booking_status import BLOCKING_BOOKING_STATUSES, BookingStatus
from app.models.role_model import Role
from app.models.room_model import Room
from app.schemas.booking_schema import BookingCreate, BookingUpdate


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class ForbiddenError(Exception):
    pass


class InvalidBookingPeriodError(ValueError):
    pass


def validate_booking_period(start_time: datetime, end_time: datetime) -> None:
    if (
        start_time.tzinfo is None
        or start_time.utcoffset() is None
        or end_time.tzinfo is None
        or end_time.utcoffset() is None
    ):
        raise InvalidBookingPeriodError("Booking dates must be timezone-aware")
    if start_time >= end_time:
        raise InvalidBookingPeriodError("Start time must be before end time")
    if start_time < datetime.now(UTC):
        raise InvalidBookingPeriodError("Booking cannot start in the past")


async def ensure_room_available(
    db: AsyncSession,
    room: Room,
    start_time: datetime,
    end_time: datetime,
    *,
    exclude_booking_id: int | None = None,
) -> None:
    query = select(func.count(Booking.id)).where(
        Booking.room_id == room.id,
        Booking.status.in_(BLOCKING_BOOKING_STATUSES),
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )
    if exclude_booking_id is not None:
        query = query.where(Booking.id != exclude_booking_id)

    booked_count = await db.scalar(query) or 0
    if booked_count >= room.total_units:
        raise ConflictError("Not enough rooms available for the selected dates")


class BookingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, booking_data: BookingCreate, user_id: int) -> Booking:
        validate_booking_period(booking_data.start_time, booking_data.end_time)
        room = await self._lock_room(booking_data.room_id)

        await ensure_room_available(
            self.db,
            room,
            booking_data.start_time,
            booking_data.end_time,
        )

        booking = Booking(
            room_id=room.id,
            user_id=user_id,
            start_time=booking_data.start_time,
            end_time=booking_data.end_time,
            status=BookingStatus.ACTIVE,
        )
        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def update(self, booking_id: int, booking_data: BookingUpdate) -> Booking:
        booking = await self._lock_booking(booking_id)
        if booking.status != BookingStatus.ACTIVE:
            raise ConflictError("Only active bookings can be updated")
        room = await self._lock_room(booking.room_id)

        start_time = booking_data.start_time or booking.start_time
        end_time = booking_data.end_time or booking.end_time
        validate_booking_period(start_time, end_time)

        await ensure_room_available(
            self.db,
            room,
            start_time,
            end_time,
            exclude_booking_id=booking.id,
        )

        booking.start_time = start_time
        booking.end_time = end_time
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def cancel(
        self,
        booking_id: int,
        *,
        requester_id: int,
        requester_role: Role,
    ) -> tuple[Booking, bool]:
        booking = await self._lock_booking(booking_id)
        if booking.user_id != requester_id and requester_role not in (
            Role.admin,
            Role.manager,
        ):
            raise ForbiddenError("You can not cancel others booking")
        if booking.status == BookingStatus.COMPLETED:
            raise ConflictError("Completed bookings cannot be cancelled")
        if booking.status == BookingStatus.CANCELLED:
            await self.db.commit()
            return booking, False

        await self._lock_room(booking.room_id, require_active=False)
        booking.status = BookingStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(booking)
        return booking, True

    async def _lock_booking(self, booking_id: int) -> Booking:
        booking = await self.db.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise NotFoundError("Booking not found")
        return booking

    async def _lock_room(self, room_id: int, *, require_active: bool = True) -> Room:
        room = await self.db.scalar(
            select(Room).where(Room.id == room_id).with_for_update()
        )
        if room is None or (require_active and not room.is_active):
            raise NotFoundError("Room not found")
        return room
