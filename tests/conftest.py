import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import insert, select
from httpx import AsyncClient, ASGITransport
from datetime import timedelta
import os
from app.models.user_model import Users
from app.main import app
from app.db.database import Base, get_db
from app.core.security import create_access_token
from app.core.config import settings

os.environ["TESTING"] = "true"

from app.celery_app import celery_app


TEST_DATABASE_URL = settings.TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL,
                                 poolclass=NullPool,
                                 echo = False)
    yield  engine
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
async def authenticated_client(client: AsyncClient, db_session: AsyncSession):
    admin_username = "AdminTest"
    admin_email="AdminTest@gmail.com"


    existing_user = await db_session.execute(select(Users).where(Users.username == admin_username))
    if not existing_user.scalar_one_or_none():
        await db_session.execute(insert(Users).values(
            username=admin_username,
            email=admin_email,
            password_hash="testhash",
            role="admin"
        ))
        await db_session.commit()

    access_token = create_access_token(
        data={"sub": admin_email, "role": "admin"},
        expires_delta=timedelta(minutes=15)
    )

    client.headers.update({"Authorization": f"Bearer {access_token}"})
    yield client