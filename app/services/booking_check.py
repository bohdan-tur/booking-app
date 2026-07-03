from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select
from app.api.dependencies import DbSession
from app.models.booking_model import Bookings
from app.models.room_model import Rooms

async def create_booking_if_available(
    db: DbSession,
    room_id: int,
    user_id: int,
    start_time: datetime,
    end_time: datetime
):

    result = await db.execute(
        select(Rooms).filter(Rooms.id == room_id).with_for_update()
    )
    room = result.scalars().first()

    if not room:
         raise HTTPException(status_code=404, detail="Room not found")


    overlap_query = await db.execute(
        select(Bookings).filter(
            Bookings.room_id == room_id,
            Bookings.start_time < end_time,
            Bookings.end_time > start_time
        )
    )
    existing_booking = overlap_query.scalars().first()

    if existing_booking:
         raise HTTPException(status_code=400, detail="Room is already booked for these dates")


    booking = Bookings(
        room_id=room_id,
        start_time=start_time,
        end_time=end_time,
        user_id=user_id
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    return booking