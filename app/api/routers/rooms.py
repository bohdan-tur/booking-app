from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import and_, func, select

from app.api.dependencies import DbSession, allow_admin, allow_admin_and_manager
from app.models.booking import Booking
from app.models.booking_status import BLOCKING_BOOKING_STATUSES
from app.models.room import Room
from app.schemas.booking import normalize_to_utc
from app.schemas.room import RoomCreate, RoomOut, RoomUpdate

router = APIRouter(tags=["Rooms"])


def resolve_period(
    start_time: datetime | None, end_time: datetime | None
) -> tuple[datetime, datetime]:
    try:
        check_start = (
            normalize_to_utc(start_time)
            if start_time is not None
            else datetime.now(UTC)
        )
        check_end = (
            normalize_to_utc(end_time)
            if end_time is not None
            else check_start + timedelta(days=1)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    if check_start >= check_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Start time must be before end time",
        )
    return check_start, check_end


@router.get("/all", status_code=status.HTTP_200_OK, response_model=list[RoomOut])
async def get_rooms_catalog(db: DbSession) -> list[RoomOut]:
    query = select(Room).where(Room.is_active.is_(True))
    rooms = await db.execute(query)
    res = rooms.scalars().all()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No rooms found in the hotel"
        )
    return res


@router.get("/available", status_code=status.HTTP_200_OK, response_model=list[RoomOut])
async def get_all_not_booked_rooms(
    db: DbSession,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> list[RoomOut]:
    check_start, check_end = resolve_period(start_time, end_time)

    booked_rooms_subq = (
        select(
            Booking.room_id,
            func.count(Booking.id).label("booked_count"),
        )
        .where(
            and_(
                Booking.status.in_(BLOCKING_BOOKING_STATUSES),
                Booking.start_time < check_end,
                Booking.end_time > check_start,
            )
        )
        .group_by(Booking.room_id)
        .subquery()
    )

    query = (
        select(Room)
        .outerjoin(booked_rooms_subq, Room.id == booked_rooms_subq.c.room_id)
        .where(
            Room.is_active.is_(True),
            (Room.total_units - func.coalesce(booked_rooms_subq.c.booked_count, 0)) > 0,
        )
    )

    rooms = await db.execute(query)
    res = rooms.scalars().all()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There aren't available rooms for the specified period",
        )

    return res


@router.get(
    "/{room_id}/available", status_code=status.HTTP_200_OK, response_model=RoomOut
)
async def get_not_booked_room(
    db: DbSession,
    room_id: Annotated[int, Path(gt=0)],
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> RoomOut:
    check_start, check_end = resolve_period(start_time, end_time)

    booked_rooms_subq = (
        select(
            Booking.room_id,
            func.count(Booking.id).label("booked_count"),
        )
        .where(
            and_(
                Booking.room_id == room_id,
                Booking.status.in_(BLOCKING_BOOKING_STATUSES),
                Booking.start_time < check_end,
                Booking.end_time > check_start,
            )
        )
        .group_by(Booking.room_id)
        .subquery()
    )

    query = (
        select(Room)
        .outerjoin(booked_rooms_subq, Room.id == booked_rooms_subq.c.room_id)
        .where(
            and_(
                Room.id == room_id,
                Room.is_active.is_(True),
                (Room.total_units - func.coalesce(booked_rooms_subq.c.booked_count, 0))
                > 0,
            )
        )
    )

    res = (await db.execute(query)).scalar()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There isn't such room or it is booked",
        )

    return res


@router.get(
    "/booked",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=list[RoomOut],
)
async def get_all_booked_rooms(
    db: DbSession,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> list[RoomOut]:
    check_start, check_end = resolve_period(start_time, end_time)

    query = (
        select(Room)
        .join(
            Booking,
            and_(
                Booking.room_id == Room.id,
                Booking.status.in_(BLOCKING_BOOKING_STATUSES),
                Booking.start_time < check_end,
                Booking.end_time > check_start,
            ),
        )
        .distinct()
    )
    rooms = await db.execute(query)
    res = rooms.scalars().all()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There aren't booked rooms for the specified period",
        )
    return res


@router.get(
    "/booked/{room_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=RoomOut,
)
async def get_booked_room(
    db: DbSession,
    room_id: Annotated[int, Path(gt=0)],
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> RoomOut:
    check_start, check_end = resolve_period(start_time, end_time)

    query = (
        select(Room)
        .join(
            Booking,
            and_(
                Booking.room_id == Room.id,
                Booking.status.in_(BLOCKING_BOOKING_STATUSES),
                Booking.start_time < check_end,
                Booking.end_time > check_start,
            ),
        )
        .filter(Room.id == room_id)
    )
    res = (await db.execute(query)).scalars().first()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room is not booked"
        )
    return res


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=RoomOut,
    dependencies=[Depends(allow_admin)],
)
async def add_room(room_data: RoomCreate, db: DbSession) -> RoomOut:
    new_room = Room(**room_data.model_dump())
    db.add(new_room)
    await db.commit()
    await db.refresh(new_room)
    return new_room


@router.patch(
    "/{room_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
)
async def change_room(
    db: DbSession, room_id: Annotated[int, Path(gt=0)], room_data: RoomUpdate
) -> dict[str, str]:
    update_data = room_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    room = await db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    new_total_units = update_data.get("total_units")
    if new_total_units is not None and new_total_units < room.total_units:
        active_booking_id = await db.scalar(
            select(Booking.id)
            .where(
                Booking.room_id == room.id,
                Booking.status.in_(BLOCKING_BOOKING_STATUSES),
                Booking.end_time > datetime.now(UTC),
            )
            .limit(1)
        )
        if active_booking_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Total units cannot be reduced while active bookings exist",
            )

    for field, value in update_data.items():
        setattr(room, field, value)
    await db.commit()
    return {"status": "success"}


@router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(allow_admin)],
)
async def delete_room_by_id(db: DbSession, room_id: Annotated[int, Path(gt=0)]) -> None:
    room = await db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )

    room.is_active = False
    await db.commit()
