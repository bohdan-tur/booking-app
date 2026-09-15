from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.booking_status import BLOCKING_BOOKING_STATUSES, BookingStatus
from app.models.role import Role
from app.models.room import Room
from app.schemas.booking import BookingCreate, BookingUpdate


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
    intervals_by_room = await _load_overlapping_intervals(
        db,
        [room.id],
        start_time,
        end_time,
        exclude_booking_id=exclude_booking_id,
    )
    if not has_available_unit(
        intervals_by_room[room.id],
        room.total_units,
        start_time,
        end_time,
    ):
        raise ConflictError("Not enough rooms available for the selected dates")


def has_available_unit(
    intervals: Sequence[tuple[datetime, datetime]],
    total_units: int,
    start_time: datetime,
    end_time: datetime,
) -> bool:
    if total_units <= 0:
        return False

    events: list[tuple[datetime, int]] = []
    for booking_start, booking_end in intervals:
        overlap_start = max(booking_start, start_time)
        overlap_end = min(booking_end, end_time)
        if overlap_start < overlap_end:
            events.append((overlap_start, 1))
            events.append((overlap_end, -1))

    events.sort(key=lambda event: (event[0], event[1]))

    current_occupancy = 0
    for _, change in events:
        current_occupancy += change
        if current_occupancy >= total_units:
            return False
    return True


async def find_available_rooms(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    *,
    room_id: int | None = None,
) -> list[Room]:
    rooms_query = select(Room).where(Room.is_active.is_(True))
    if room_id is not None:
        rooms_query = rooms_query.where(Room.id == room_id)

    rooms = list((await db.scalars(rooms_query.order_by(Room.id))).all())
    if not rooms:
        return []

    intervals_by_room = await _load_overlapping_intervals(
        db,
        [room.id for room in rooms],
        start_time,
        end_time,
    )
    return [
        room
        for room in rooms
        if has_available_unit(
            intervals_by_room[room.id],
            room.total_units,
            start_time,
            end_time,
        )
    ]


async def _load_overlapping_intervals(
    db: AsyncSession,
    room_ids: Sequence[int],
    start_time: datetime,
    end_time: datetime,
    *,
    exclude_booking_id: int | None = None,
) -> dict[int, list[tuple[datetime, datetime]]]:
    query = select(Booking.room_id, Booking.start_time, Booking.end_time).where(
        Booking.room_id.in_(room_ids),
        Booking.status.in_(BLOCKING_BOOKING_STATUSES),
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )
    if exclude_booking_id is not None:
        query = query.where(Booking.id != exclude_booking_id)

    intervals_by_room: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
    for booked_room_id, booking_start, booking_end in (await db.execute(query)).all():
        intervals_by_room[booked_room_id].append((booking_start, booking_end))
    return intervals_by_room


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
