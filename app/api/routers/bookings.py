from typing import Annotated

from celery import Task
from celery.exceptions import CeleryError
from fastapi import APIRouter, Depends, HTTPException, status
from kombu.exceptions import OperationalError as BrokerOperationalError
from sqlalchemy import select

from app.api.dependencies import DbSession, allow_admin_and_manager, get_current_user
from app.core.logger import logger
from app.models.booking import Booking
from app.models.role import Role
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut, BookingUpdate
from app.services.booking_service import (
    BookingService,
    ConflictError,
    ForbiddenError,
    InvalidBookingPeriodError,
    NotFoundError,
)
from app.workers.tasks import process_booking_cancellation, process_booking_creation

router = APIRouter(tags=["Bookings"])


def _enqueue_booking_notification(task: Task, *, booking_id: int) -> None:
    try:
        task.delay(booking_id=booking_id)
    except (BrokerOperationalError, CeleryError):
        logger.warning(
            "Failed to enqueue booking notification: task=%s booking_id=%s",
            task.name,
            booking_id,
        )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookingOut)
async def book_room(
    booking_data: BookingCreate,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> BookingOut:
    try:
        booking = await BookingService(db).create(booking_data, user.id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidBookingPeriodError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    _enqueue_booking_notification(process_booking_creation, booking_id=booking.id)

    return booking


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=list[BookingOut],
)
async def get_all_bookings(db: DbSession) -> list[BookingOut]:
    bookings = await db.execute(select(Booking))
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
    current_user: Annotated[User, Depends(get_current_user)],
) -> BookingOut:
    bookings = await db.execute(select(Booking).filter(Booking.id == booking_id))
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

    try:
        await BookingService(db).update(booking_id, booking_to_update)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidBookingPeriodError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return {"status": "success"}


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    try:
        booking, changed = await BookingService(db).cancel(
            booking_id,
            requester_id=current_user.id,
            requester_role=current_user.role,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if changed:
        _enqueue_booking_notification(
            process_booking_cancellation,
            booking_id=booking.id,
        )
