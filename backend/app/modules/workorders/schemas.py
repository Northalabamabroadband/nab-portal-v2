from datetime import datetime

from pydantic import BaseModel, Field


PRIORITY_PATTERN = "^(low|normal|high|critical|urgent)$"


class WorkOrderCreate(BaseModel):
    client_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=3, max_length=220)
    description: str = Field(default="", max_length=10000)
    priority: str = Field(default="normal", pattern=PRIORITY_PATTERN)
    assigned_technician: str | None = Field(default=None, max_length=320)
    service_address: str | None = Field(default=None, max_length=500)
    scheduled_for: datetime | None = None


class WorkOrderUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(open|scheduled|in_progress|completed|cancelled)$",
    )
    priority: str | None = Field(default=None, pattern=PRIORITY_PATTERN)
    assigned_technician: str | None = Field(default=None, max_length=320)
    scheduled_for: datetime | None = None


class WorkOrderRead(BaseModel):
    id: str
    client_id: str | None
    title: str
    description: str
    status: str
    priority: str
    assigned_technician: str | None
    service_address: str | None
    scheduled_for: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
