from datetime import UTC, datetime

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from app.models.booking_status import BookingStatus


def normalize_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a timezone offset")
    return value.astimezone(UTC)


class BookingValidationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("start_time", "end_time", mode="after", check_fields=False)
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return normalize_to_utc(value) if value is not None else None

    @model_validator(mode="after")
    def check_dates(self):
        start_time = getattr(self, "start_time", None)
        end_time = getattr(self, "end_time", None)

        if start_time is not None and end_time is not None and start_time >= end_time:
            raise ValueError("Start time must be before end time")
        return self


class BookingCreate(BookingValidationBase):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "room_id": 1,
                "start_time": "2030-08-15T14:00:00Z",
                "end_time": "2030-08-20T11:00:00Z",
            }
        },
    )

    room_id: int
    start_time: AwareDatetime
    end_time: AwareDatetime


class BookingUpdate(BookingValidationBase):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "start_time": "2030-08-15T14:00:00Z",
                "end_time": "2030-08-20T11:00:00Z",
            }
        },
    )

    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    user_id: int
    start_time: AwareDatetime
    end_time: AwareDatetime
    status: BookingStatus
