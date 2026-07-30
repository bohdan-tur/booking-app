from enum import StrEnum


class BookingStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


BLOCKING_BOOKING_STATUSES = (BookingStatus.ACTIVE,)
