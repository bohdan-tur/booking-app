import os
import uuid
from datetime import timedelta

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.core.config import settings
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.main import app
from app.models.user_model import Users
from app.models.room_model import Rooms
from app.models.booking_model import Bookings

os.environ["TESTING"] = "true"

TEST_DATABASE_URL = settings.TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(engine):
    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def override_get_db(engine):
    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async def _override():
        async with async_session() as session:
            yield session
            await session.close()

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def create_test_user(db_session: AsyncSession):
    async def _create_user(role="admin"):
        unique_suffix = uuid.uuid4().hex[:8]
        user = Users(
            username=f"tester_{unique_suffix}",
            email=f"tester_{unique_suffix}@example.com",
            password_hash="testhash",
            role=role,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create_user


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient, create_test_user):

    user = await create_test_user(role="admin")


    access_token = create_access_token(
        {"sub": str(user.id), "role": user.role},
        timedelta(minutes=15)
    )

    client.headers.update({"Authorization": f"Bearer {access_token}"})
    yield client





@pytest_asyncio.fixture
async def create_room(db_session: AsyncSession):

    async def _create_room(name="Default Room", price=1000, capacity=2, location="Lviv", quantity=1, amenities="WiFi"):
        room = Rooms(
            name=name, price=price, capacity=capacity,
            location=location, quantity=quantity, amenities=amenities
        )
        db_session.add(room)
        await db_session.commit()
        await db_session.refresh(room)
        return room
    return _create_room


@pytest_asyncio.fixture
async def create_booking(db_session: AsyncSession):

    async def _create_booking(user_id: int, room_id: int, start_time, end_time):
        booking = Bookings(
            user_id=user_id, room_id=room_id,
            start_time=start_time, end_time=end_time
        )
        db_session.add(booking)
        await db_session.commit()
        await db_session.refresh(booking)
        return booking
    return _create_booking