from datetime import datetime
from pydantic import BaseModel, Field


class InventoryCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=2, max_length=220)
    category: str = Field(default="General", max_length=120)
    quantity_on_hand: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=0, ge=0)
    location: str | None = Field(default=None, max_length=220)
    serial_tracking: str = Field(default="optional", pattern="^(none|optional|required)$")


class InventoryAdjust(BaseModel):
    delta: int = Field(ge=-100000, le=100000)


class InventoryRead(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    quantity_on_hand: int
    reorder_level: int
    location: str | None
    serial_tracking: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
