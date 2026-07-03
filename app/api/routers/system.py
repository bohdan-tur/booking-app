import asyncio

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.dependencies import DbSession

router = APIRouter(tags=["System"])


@router.get("/live", summary="Liveness Probe")
async def liveness_check(response: Response):

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return {"status": "pass"}


@router.get("/ready", summary="Readiness Probe")
async def readiness_check(response: Response, db: DbSession):

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    components = {}
    is_ready = True

    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
        components["database"] = {"status": "pass"}
    except Exception as e:
        components["database"] = {"status": "fail", "detail": str(e)}
        is_ready = False

    payload = {"status": "pass" if is_ready else "fail", "checks": components}

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return payload