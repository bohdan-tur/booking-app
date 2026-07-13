from fastapi import HTTPException, status
from sqlalchemy import select
from app.api.dependencies import DbSession
from app.models.booking_model import Bookings
from app.models.room_model import Rooms
from app.schemas.booking_schema import BookingCreate
from sqlalchemy import and_, func


async def create_booking_if_available(
    db: DbSession,
    booking_data: BookingCreate,
    user_id: int,
):
    room = await db.execute(select(Rooms).where(Rooms.id == booking_data.room_id))
    target_room = room.scalar_one_or_none()

    if not target_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    overlapping_bookings = await db.execute(
        select(func.count(Bookings.id)).where(
            and_(
                Bookings.room_id == booking_data.room_id,
                Bookings.start_time < booking_data.end_time,
                Bookings.end_time > booking_data.start_time,
            )
        )
    )

    booked_count = overlapping_bookings.scalar() or 0

    if booked_count >= target_room.quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Not enough rooms of this category available for the selected dates.",
        )

    new_booking = Bookings(
        room_id=booking_data.room_id,
        user_id=user_id,
        start_time=booking_data.start_time,
        end_time=booking_data.end_time,
    )

    db.add(new_booking)
    await db.commit()
    await db.refresh(new_booking)

    return new_booking
