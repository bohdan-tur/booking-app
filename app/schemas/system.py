from pydantic import BaseModel, ConfigDict


class LivenessResponse(BaseModel):
    status: str = "pass"

    model_config = ConfigDict(from_attributes=True)


class HealthCheckComponent(BaseModel):
    status: str
    detail: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, HealthCheckComponent]

    model_config = ConfigDict(from_attributes=True)
