from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, model_validator


class BookingBase(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

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


class BookingOut(BookingBase):
    id: int
    room_id: int
    user_id: int
    status: str = Field(default="Booked")


class BookingUpdate(BookingBase):
    start_time: datetime | None = None
    end_time: datetime | None = None