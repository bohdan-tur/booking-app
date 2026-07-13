from datetime import datetime, UTC, timedelta
from typing import Annotated, List

from fastapi import APIRouter, Depends, status, HTTPException, Path, Query
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.dependencies import allow_admin, allow_admin_and_manager
from app.models.booking_model import Bookings
from app.models.room_model import Rooms
from app.schemas.room_schema import RoomCreate, RoomOut, RoomUpdate

db_dependency = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(tags=["Rooms"])


@router.get("/all", status_code=status.HTTP_200_OK, response_model=List[RoomOut])
async def get_rooms_catalog(db: db_dependency):
    query = select(Rooms)
    rooms = await db.execute(query)
    res = rooms.scalars().all()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No rooms found in the hotel"
        )
    return res


@router.get("/available", status_code=status.HTTP_200_OK, response_model=List[RoomOut])
async def get_all_not_booked_rooms(
    db: db_dependency,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
):
    check_start = start_time if start_time else datetime.now(UTC).replace(tzinfo=None)
    check_end = end_time if end_time else check_start + timedelta(days=1)

    booked_rooms_subq = (
        select(
            Bookings.room_id,
            func.count(Bookings.id).label("booked_count"),
        )
        .where(
            and_(
                Bookings.start_time < check_end,
                Bookings.end_time > check_start,
            )
        )
        .group_by(Bookings.room_id)
        .subquery()
    )

    query = (
        select(Rooms)
        .outerjoin(booked_rooms_subq, Rooms.id == booked_rooms_subq.c.room_id)
        .where(
            (Rooms.quantity - func.coalesce(booked_rooms_subq.c.booked_count, 0)) > 0
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
    db: db_dependency,
    room_id: Annotated[int, Path(gt=0)],
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
):
    check_start = start_time if start_time else datetime.now(UTC).replace(tzinfo=None)
    check_end = end_time if end_time else check_start + timedelta(days=1)

    booked_rooms_subq = (
        select(
            Bookings.room_id,
            func.count(Bookings.id).label("booked_count"),
        )
        .where(
            and_(
                Bookings.room_id == room_id,
                Bookings.start_time < check_end,
                Bookings.end_time > check_start,
            )
        )
        .group_by(Bookings.room_id)
        .subquery()
    )

    query = (
        select(Rooms)
        .outerjoin(booked_rooms_subq, Rooms.id == booked_rooms_subq.c.room_id)
        .where(
            and_(
                Rooms.id == room_id,
                (Rooms.quantity - func.coalesce(booked_rooms_subq.c.booked_count, 0))
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
    response_model=List[RoomOut],
)
async def get_all_booked_rooms(
    db: db_dependency,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
):
    check_start = start_time if start_time else datetime.now(UTC).replace(tzinfo=None)
    check_end = end_time if end_time else check_start + timedelta(days=1)

    query = (
        select(Rooms)
        .join(
            Bookings,
            and_(
                Bookings.room_id == Rooms.id,
                Bookings.start_time < check_end,
                Bookings.end_time > check_start,
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
    db: db_dependency,
    room_id: Annotated[int, Path(gt=0)],
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
):
    check_start = start_time if start_time else datetime.now(UTC).replace(tzinfo=None)
    check_end = end_time if end_time else check_start + timedelta(days=1)

    query = (
        select(Rooms)
        .join(
            Bookings,
            and_(
                Bookings.room_id == Rooms.id,
                Bookings.start_time < check_end,
                Bookings.end_time > check_start,
            ),
        )
        .filter(Rooms.id == room_id)
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
async def add_room(room_data: RoomCreate, db: db_dependency):
    new_room = Rooms(**room_data.model_dump())
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
    db: db_dependency, room_id: Annotated[int, Path(gt=0)], room_data: RoomUpdate
):
    update_data = room_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    changed_room = await db.execute(
        update(Rooms)
        .filter(Rooms.id == room_id)
        .values(**update_data)
        .returning(Rooms.id)
    )

    res = changed_room.scalar()
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    await db.commit()
    return {"status": "success"}


@router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(allow_admin)],
)
async def delete_room_by_id(db: db_dependency, room_id: Annotated[int, Path(gt=0)]):
    deleted_room = await db.execute(
        delete(Rooms).filter(Rooms.id == room_id).returning(Rooms.id)
    )
    res = deleted_room.scalars().first()

    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )

    await db.commit()
    return None
