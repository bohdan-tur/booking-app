from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete, update

from app.api.dependencies import DbSession
from app.api.dependencies import get_current_user, allow_admin_and_manager
from app.models.booking_model import Bookings
from app.models.role_model import Role
from app.models.user_model import Users
from app.schemas.booking_schema import BookingOut, BookingUpdate
from app.services.booking_check import create_booking_if_available

router = APIRouter(tags=['Bookings'])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookingOut)
async def book_room(
        room_id_to_book: int,
        start_time: datetime,
        end_time: datetime,
        db: DbSession,
        user: Annotated[Users, Depends(get_current_user)]
):
    booking = await create_booking_if_available(
        db=db,
        room_id=room_id_to_book,
        user_id=user.id,
        start_time=start_time,
        end_time=end_time
    )

    return booking


@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(allow_admin_and_manager)])
async def get_all_bookings(db: DbSession):
    bookings = await db.execute(select(Bookings))
    result = bookings.scalars().all()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="There are not any bookings.")

    return result


@router.get("/{booking_id}", status_code=status.HTTP_200_OK)
async def get_single_booking(
        booking_id: int,
        db: DbSession,
        current_user: Annotated[Users, Depends(get_current_user)]
):
    bookings = await db.execute(select(Bookings).filter(Bookings.id == booking_id))
    result = bookings.scalars().first()

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if result.user_id != current_user.id and current_user.role not in (Role.admin, Role.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can not view others booking")

    return result


@router.patch("/{booking_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(allow_admin_and_manager)])
async def update_booking(
        booking_id: int,
        booking_to_update: BookingUpdate,
        db: DbSession
):
    updated_booking = await db.execute(
        update(Bookings)
        .filter(Bookings.id == booking_id)
        .values(
            start_time=booking_to_update.start_time,
            end_time=booking_to_update.end_time,
        ).returning(Bookings.id)
    )

    res = updated_booking.scalar()
    if res is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    await db.commit()
    return {"status": "success"}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
        id: int,
        db: DbSession,
        current_user: Annotated[Users, Depends(get_current_user)]
):
    booking_to_delete = await db.execute(delete(Bookings).where(Bookings.id == id).returning(Bookings))
    result = booking_to_delete.scalars().first()

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if result.user_id != current_user.id and current_user.role not in (Role.admin, Role.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can not cancel others booking")

    await db.commit()