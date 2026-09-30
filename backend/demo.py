import math
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .database import Camera, Zone, Incident


def seed(session):
    if session.scalar(select(Camera.id).limit(1)):
        return
    names = [
        ("Сборочный цех", "Корпус А · Участок 01"),
        ("Зона погрузки", "Корпус Б · Склад"),
        ("Линия металлообработки", "Корпус А · Участок 03"),
        ("Склад готовой продукции", "Корпус В · Склад"),
    ]
    for i, (name, location) in enumerate(names):
        session.add(
            Camera(
                id=f"cam-0{i+1}", name=name, location=location, source="demo", demo=True
            )
        )
    session.add(
        Zone(
            id="zone-01",
            camera_id="cam-01",
            name="Зона работы пресса",
            points=[[0.59, 0.49], [0.82, 0.49], [0.95, 0.90], [0.55, 0.90]],
            enabled=True,
        )
    )
    now = datetime.now(timezone.utc)
    kinds = ["no_helmet", "zone", "no_vest", "no_helmet", "fall", "no_vest"]
    for i in range(47):
        kind = kinds[i % len(kinds)]
        started = now - timedelta(minutes=5 + i * 19)
        session.add(
            Incident(
                id=f"demo-{i:04}",
                camera_id=f"cam-0{i%4+1}",
                camera_name=names[i % 4][0],
                track_id=12 + i % 17,
                kind=kind,
                severity="critical" if kind in ("fall", "zone") else "warning",
                status="new" if i < 4 else "acknowledged" if i < 9 else "resolved",
                started_at=started.isoformat(),
                ended_at=(started + timedelta(seconds=15 + i % 70)).isoformat(),
                confidence=0.88 + (i % 11) / 100,
                zone_name="Зона работы пресса" if kind == "zone" else "",
                note="",
                demo=True,
            )
        )
    session.commit()


def demo_tracks(camera_id, tick):
    offset = sum(map(ord, camera_id)) % 7
    tracks = []
    for i in range(3):
        x = 0.19 + i * 0.22 + math.sin(tick * 0.16 + i + offset) * 0.025
        y = 0.44 + (i % 2) * 0.11
        # Violation cycles stay stable long enough to exercise real debounce.
        unsafe = i == 1 and int(tick / 20 + offset) % 3 == 0
        tracks.append(
            {
                "id": 12 + i,
                "bbox": [x, y, x + 0.065, y + 0.24],
                "helmet": not unsafe,
                "vest": True,
                "confidence": 0.94 + i * 0.015,
            }
        )
    return tracks
