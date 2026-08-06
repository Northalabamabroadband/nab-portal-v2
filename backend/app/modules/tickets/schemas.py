from datetime import datetime

from pydantic import BaseModel, Field


PRIORITY_PATTERN = "^(low|normal|high|critical|urgent)$"


class TicketCreate(BaseModel):
    client_id: str | None = Field(default=None, max_length=64)
    subject: str = Field(min_length=3, max_length=220)
    description: str = Field(default="", max_length=10000)
    priority: str = Field(default="normal", pattern=PRIORITY_PATTERN)
    assigned_to: str | None = Field(default=None, max_length=320)


class TicketUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(open|pending|in_progress|resolved|closed)$",
    )
    priority: str | None = Field(default=None, pattern=PRIORITY_PATTERN)
    assigned_to: str | None = Field(default=None, max_length=320)


class TicketRead(BaseModel):
    id: str
    client_id: str | None
    subject: str
    description: str
    status: str
    priority: str
    assigned_to: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
