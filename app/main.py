import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import auth, bookings, rooms, system, users
from app.core.config import Environment, settings
from app.core.logger import logger
from app.db.seed import seed_data
from app.services.rate_limit_service import close_rate_limiter


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("🚀 Starting API and initializing resources...")

    if settings.ENVIRONMENT is Environment.development and settings.SEED_DEFAULT_USERS:
        try:
            await seed_data()
            logger.info("✅ Database seeded successfully.")
        except SQLAlchemyError:
            logger.exception("❌ Error during database seeding")

    yield

    await close_rate_limiter()
    logger.info("🛑 Shutting down API and cleaning up resources...")


app = FastAPI(
    title="Booking API",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    logger.info(
        f"Method: {request.method} | "
        f"Path: {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Time: {process_time:.4f}s"
    )
    return response


app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
app.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
app.include_router(system.router, prefix="/system", tags=["System"])
