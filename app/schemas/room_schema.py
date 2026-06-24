from pydantic import BaseModel, Field, ConfigDict

class RoomBase(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str | None = None
    price: int = Field(gt=0)
    capacity: int = Field(ge=1, le=10)
    amenities: str | None = None
    quantity: int = Field(ge=0)
    location: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "Lux Double Room",
                "description": "Magnificent room with a city center view",
                "price": 2500,
                "capacity": 2,
                "amenities": "Wi-Fi, Air conditioning, Breakfast",
                "quantity": 5,
                "location": "Lviv, Teatralna St, 15"
            }
        }
    )

class RoomCreate(RoomBase):
    pass

class RoomOut(RoomBase):
    id: int