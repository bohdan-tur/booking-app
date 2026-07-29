from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookingValidationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
                "start_time": "2024-07-15T14:00:00",
                "end_time": "2024-07-20T11:00:00",
            }
        },
    )

    room_id: int
    start_time: datetime
    end_time: datetime


class BookingUpdate(BookingValidationBase):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "start_time": "2024-07-15T14:00:00",
                "end_time": "2024-07-20T11:00:00",
            }
        },
    )

    start_time: datetime | None = None
    end_time: datetime | None = None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: str = Field(default="Booked")
