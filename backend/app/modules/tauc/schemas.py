from pydantic import BaseModel, Field


class DeviceLookupRequest(BaseModel):
    serial_number: str = Field(min_length=4, max_length=128)
    mac_address: str | None = Field(default=None, max_length=32)


class GatewayMappingRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)
    serial_number: str = Field(min_length=4, max_length=128)
    mac_address: str | None = Field(default=None, max_length=32)
