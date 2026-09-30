import math
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, field_validator


class CameraInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    location: str = Field(min_length=2, max_length=100)
    source: str = Field(default="demo", max_length=1000)
    enabled: bool = True

    @field_validator("source")
    @classmethod
    def source_valid(cls, value):
        if value != "demo":
            parsed = urlsplit(value)
            if parsed.scheme not in ("rtsp", "rtsps") or not parsed.hostname:
                raise ValueError("Требуется RTSP-адрес камеры или demo")
        return value


class ZoneInput(BaseModel):
    camera_id: str
    name: str = Field(min_length=2, max_length=100)
    points: list[tuple[float, float]] = Field(min_length=3, max_length=32)
    enabled: bool = True

    @field_validator("points")
    @classmethod
    def validate_polygon(cls, points):
        if any(not math.isfinite(v) or not 0 <= v <= 1 for p in points for v in p):
            raise ValueError("Координаты должны быть в диапазоне 0…1")
        if len(set(points)) != len(points):
            raise ValueError("Вершины не должны повторяться")

        def orient(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        edges = [(p, points[(i + 1) % len(points)]) for i, p in enumerate(points)]
        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges):
                if j <= i or j == i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                if (
                    orient(a, b, c) * orient(a, b, d) <= 0
                    and orient(c, d, a) * orient(c, d, b) <= 0
                ):
                    if max(min(a[0], b[0]), min(c[0], d[0])) <= min(
                        max(a[0], b[0]), max(c[0], d[0])
                    ) and max(min(a[1], b[1]), min(c[1], d[1])) <= min(
                        max(a[1], b[1]), max(c[1], d[1])
                    ):
                        raise ValueError("Границы зоны не должны пересекаться")
        area = sum(
            p[0] * points[(i + 1) % len(points)][1]
            - points[(i + 1) % len(points)][0] * p[1]
            for i, p in enumerate(points)
        )
        if abs(area) < 0.0001:
            raise ValueError("Зона должна иметь ненулевую площадь")
        return points


class IncidentUpdate(BaseModel):
    status: Literal["new", "acknowledged", "resolved"]
    note: str = Field(default="", max_length=2000)


class TrackInput(BaseModel):
    id: int = Field(ge=0)
    bbox: tuple[float, float, float, float]
    confidence: float = Field(ge=0, le=1)
    helmet: bool | None = None
    vest: bool | None = None
    fall: bool | None = None
    pose: list[list[float]] | None = None

    @field_validator("bbox")
    @classmethod
    def bbox_valid(cls, box):
        if (
            any(not math.isfinite(v) or not 0 <= v <= 1 for v in box)
            or box[2] <= box[0]
            or box[3] <= box[1]
        ):
            raise ValueError("Некорректная рамка")
        return box


class FrameInput(BaseModel):
    camera_id: str
    tracks: list[TrackInput] = Field(max_length=200)
    latency_ms: float = Field(ge=0, le=60000)
    fps: float = Field(ge=0, le=120)
