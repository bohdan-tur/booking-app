from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RoomBase(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    capacity: int = Field(ge=1, le=10)
    amenities: str | None = None
    total_units: int = Field(ge=0)
    location: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "Lux Double Room",
                "description": "Magnificent room with a city center view",
                "price": "2500.00",
                "capacity": 2,
                "amenities": "Wi-Fi, Air conditioning, Breakfast",
                "total_units": 5,
                "location": "Lviv, Teatralna St, 15",
            }
        },
    )


class RoomCreate(RoomBase):
    pass


class RoomOut(RoomBase):
    id: int
    is_active: bool


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    capacity: int | None = Field(default=None, ge=1, le=10)
    amenities: str | None = None
    total_units: int | None = Field(default=None, ge=0)
    location: str | None = None

    model_config = ConfigDict(extra="forbid")
