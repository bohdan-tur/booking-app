from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update

from app.api.dependencies import DbSession, allow_admin_and_manager, get_current_user
from app.models.booking_model import Bookings
from app.models.role_model import Role
from app.models.user_model import Users
from app.schemas.booking_schema import BookingCreate, BookingOut, BookingUpdate
from app.services.booking_check import create_booking_if_available
from app.workers.tasks import process_booking_cancellation, process_booking_creation

router = APIRouter(tags=["Bookings"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookingOut)
async def book_room(
    booking_data: BookingCreate,
    db: DbSession,
    user: Annotated[Users, Depends(get_current_user)],
) -> BookingOut:
    booking = await create_booking_if_available(
        db=db,
        booking_data=booking_data,
        user_id=user.id,
    )

    process_booking_creation.delay(
        booking_id=booking.id,
        user_id=booking.user_id,
        room_id=booking.room_id,
        start_time=booking.start_time,
        end_time=booking.end_time,
    )

    return booking


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=list[BookingOut],
)
async def get_all_bookings(db: DbSession) -> list[BookingOut]:
    bookings = await db.execute(select(Bookings))
    result = bookings.scalars().all()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="There are not any bookings."
        )

    return result


@router.get("/{booking_id}", status_code=status.HTTP_200_OK, response_model=BookingOut)
async def get_single_booking(
    booking_id: int,
    db: DbSession,
    current_user: Annotated[Users, Depends(get_current_user)],
) -> BookingOut:
    bookings = await db.execute(select(Bookings).filter(Bookings.id == booking_id))
    result = bookings.scalars().first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found."
        )

    if result.user_id != current_user.id and current_user.role not in (
        Role.admin,
        Role.manager,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can not view others booking",
        )

    return result


@router.patch(
    "/{booking_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
)
async def update_booking(
    booking_id: int, booking_to_update: BookingUpdate, db: DbSession
) -> dict[str, str]:
    update_data = booking_to_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    updated_booking = await db.execute(
        update(Bookings)
        .filter(Bookings.id == booking_id)
        .values(**update_data)
        .returning(Bookings.id)
    )

    res = updated_booking.scalar()
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )

    await db.commit()
    return {"status": "success"}


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: int,
    db: DbSession,
    current_user: Annotated[Users, Depends(get_current_user)],
) -> None:
    booking_to_delete = await db.execute(
        delete(Bookings).where(Bookings.id == booking_id).returning(Bookings)
    )
    result = booking_to_delete.scalar_one_or_none()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )

    if result.user_id != current_user.id and current_user.role not in (
        Role.admin,
        Role.manager,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can not cancel others booking",
        )

    task_booking_id = result.id
    task_user_id = result.user_id

    await db.commit()

    process_booking_cancellation.delay(booking_id=task_booking_id, user_id=task_user_id)
