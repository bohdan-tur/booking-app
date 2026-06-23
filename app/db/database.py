import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()
URL = os.getenv("URL")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

engine = create_async_engine(URL, echo=DEBUG)

AsyncSessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class Base(DeclarativeBase):
    pass