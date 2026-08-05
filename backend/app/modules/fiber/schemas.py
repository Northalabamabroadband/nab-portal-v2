from datetime import datetime
from pydantic import BaseModel, Field


ASSET_TYPES = "^(cabinet|pole|handhole|vault|splitter|olt|ont|splice_enclosure|slack_loop|patch_panel|conduit)$"
ASSET_STATUS = "^(planned|active|warning|damaged|offline|retired)$"
ROUTE_STATUS = "^(planned|construction|active|damaged|retired)$"


class FiberAssetCreate(BaseModel):
    asset_type: str = Field(pattern=ASSET_TYPES)
    name: str = Field(min_length=2, max_length=220)
    asset_code: str = Field(min_length=1, max_length=120)
    status: str = Field(default="active", pattern=ASSET_STATUS)
    location_name: str | None = Field(default=None, max_length=220)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    parent_asset_id: str | None = Field(default=None, max_length=36)
    client_id: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=160)
    model: str | None = Field(default=None, max_length=160)
    serial_number: str | None = Field(default=None, max_length=180)
    strand_count: int | None = Field(default=None, ge=0)
    used_capacity: int = Field(default=0, ge=0)
    total_capacity: int = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=10000)
    installed_at: datetime | None = None


class FiberAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=220)
    status: str | None = Field(default=None, pattern=ASSET_STATUS)
    location_name: str | None = Field(default=None, max_length=220)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    parent_asset_id: str | None = Field(default=None, max_length=36)
    client_id: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=160)
    model: str | None = Field(default=None, max_length=160)
    serial_number: str | None = Field(default=None, max_length=180)
    strand_count: int | None = Field(default=None, ge=0)
    used_capacity: int | None = Field(default=None, ge=0)
    total_capacity: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=10000)
    retired: bool | None = None


class FiberAssetRead(FiberAssetCreate):
    id: str
    retired: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FiberRouteCreate(BaseModel):
    route_code: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=2, max_length=220)
    status: str = Field(default="planned", pattern=ROUTE_STATUS)
    cable_type: str | None = Field(default=None, max_length=120)
    strand_count: int = Field(default=0, ge=0)
    length_feet: float = Field(default=0, ge=0)
    start_location: str | None = Field(default=None, max_length=220)
    end_location: str | None = Field(default=None, max_length=220)
    ownership: str | None = Field(default=None, max_length=160)
    notes: str = Field(default="", max_length=10000)


class FiberRouteRead(FiberRouteCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
