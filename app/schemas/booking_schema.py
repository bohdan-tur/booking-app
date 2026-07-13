from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, model_validator


class BookingBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "start_time": "2024-07-15T14:00:00",
                "end_time": "2024-07-20T11:00:00",
            }
        },
    )

    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("Start time must be before end time")
        return self


class BookingCreate(BookingBase):
    room_id: int


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: str = Field(default="Booked")


class BookingUpdate(BookingBase):
    start_time: datetime | None = None
    end_time: datetime | None = None
