from typing import Any

from pydantic import BaseModel, Field, field_validator


class RouteGeometryWrite(BaseModel):
    geometry: dict[str, Any]
    source: str = Field(default="manual", max_length=80)

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("type") != "LineString":
            raise ValueError("Geometry must be a GeoJSON LineString")

        coordinates = value.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError("LineString requires at least two coordinates")

        for coordinate in coordinates:
            if (
                not isinstance(coordinate, list)
                or len(coordinate) < 2
                or not isinstance(coordinate[0], (int, float))
                or not isinstance(coordinate[1], (int, float))
            ):
                raise ValueError("Each coordinate must be [longitude, latitude]")

            longitude, latitude = coordinate[0], coordinate[1]
            if longitude < -180 or longitude > 180:
                raise ValueError("Longitude must be between -180 and 180")
            if latitude < -90 or latitude > 90:
                raise ValueError("Latitude must be between -90 and 90")

        return value
