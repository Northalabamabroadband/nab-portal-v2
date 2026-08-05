from datetime import datetime
from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    title: str = Field(min_length=2, max_length=220)
    message: str = Field(default="", max_length=10000)
    severity: str = Field(default="info", pattern="^(info|warning|critical)$")
    source: str = Field(default="portal", min_length=1, max_length=120)
    resource_type: str | None = Field(default=None, max_length=80)
    resource_id: str | None = Field(default=None, max_length=160)


class AlertRead(BaseModel):
    id: str
    title: str
    message: str
    severity: str
    source: str
    resource_type: str | None
    resource_id: str | None
    acknowledged: bool
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
