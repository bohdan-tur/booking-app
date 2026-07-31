import asyncio

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.dependencies import DbSession
from app.schemas.system import (
    HealthCheckComponent,
    LivenessResponse,
    ReadinessResponse,
)

router = APIRouter(tags=["System"])


@router.get("/live", summary="Liveness Probe")
async def liveness_check(response: Response) -> LivenessResponse:

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return LivenessResponse()


@router.get("/ready", summary="Readiness Probe")
async def readiness_check(response: Response, db: DbSession) -> ReadinessResponse:

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    checks: dict[str, HealthCheckComponent] = {}
    is_ready = True

    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
        checks["database"] = HealthCheckComponent(status="pass")
    # A readiness probe must report every dependency failure as 503 instead
    # of propagating an unexpected driver error through the application.
    except Exception as e:  # noqa: BLE001
        checks["database"] = HealthCheckComponent(status="fail", detail=str(e))
        is_ready = False

    readiness_response = ReadinessResponse(
        status="pass" if is_ready else "fail", checks=checks
    )

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return readiness_response
