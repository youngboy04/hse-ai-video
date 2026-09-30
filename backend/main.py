import asyncio
import csv
import io
import json
import logging
import os
import secrets
import time
from collections import Counter, defaultdict
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import (
    FastAPI,
    Depends,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.responses import FileResponse, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .database import (
    Base,
    engine,
    Session,
    Camera,
    Zone,
    Incident,
    Outbox,
    MediaOutbox,
    asdict,
    utcnow,
)
from .schemas import CameraInput, ZoneInput, IncidentUpdate, FrameInput
from .logic import DebounceEngine, violations_for
from .demo import seed, demo_tracks
from .storage import save_media, get_path, mirror

logger = logging.getLogger("hse")
DEMO = os.getenv("DEMO_MODE", "true").lower() == "true"
OPERATOR_TOKEN = os.getenv("OPERATOR_TOKEN", "")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "local-development-change-me")
MEDIA = Path(os.getenv("MEDIA_DIR", "./data/snapshots"))
debouncer = DebounceEngine(
    float(os.getenv("DEBOUNCE_SECONDS", "2")),
    float(os.getenv("CLOSE_AFTER_SECONDS", "3")),
)
live: dict[str, dict] = {}
subscribers: dict[str, set] = defaultdict(set)


def authorize(authorization: str | None = Header(default=None)):
    if OPERATOR_TOKEN and not secrets.compare_digest(
        authorization or "", f"Bearer {OPERATOR_TOKEN}"
    ):
        raise HTTPException(401, "Введите ключ доступа в настройках подключения")


def service_auth(x_service_token: str | None = Header(default=None)):
    if not secrets.compare_digest(x_service_token or "", SERVICE_TOKEN):
        raise HTTPException(401, "Invalid service token")


def broadcast(room, payload, jpeg=None):
    for queue in list(subscribers[room]):
        if queue.full():
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        queue.put_nowait((payload, jpeg))


def camera_dict(camera):
    status = live.get(camera.id, {})
    online = camera.enabled and time.time() - status.get("received", 0) < 8
    data = asdict(camera)
    # Camera credentials are available only to the ingestion service.
    data["source"] = "demo" if camera.demo else "rtsp://••••••"
    return {
        **data,
        "online": online,
        "fps": round(status.get("fps", 0), 1) if online else 0,
        "latency_ms": round(status.get("latency_ms", 0)) if online else 0,
    }


def apply_events(session, camera, events, jpeg):
    for event in events:
        if event["action"] == "open":
            snapshot = None
            if jpeg:
                key = f"{event['id']}.jpg"
                save_media(key, jpeg, "image/jpeg")
                if os.getenv("S3_ENDPOINT"):
                    session.add(MediaOutbox(key=key, content_type="image/jpeg"))
                snapshot = f"/api/snapshots/{event['id']}"
            incident = Incident(
                id=event["id"],
                camera_id=camera.id,
                camera_name=camera.name,
                track_id=event["track_id"],
                kind=event["kind"],
                severity="critical" if event["kind"] in ("fall", "zone") else "warning",
                started_at=datetime.fromtimestamp(
                    event["started_at"], timezone.utc
                ).isoformat(),
                ended_at=None,
                confidence=event["confidence"],
                zone_name=event["zone_name"],
                status="new",
                note="",
                demo=camera.demo,
                snapshot_url=snapshot,
            )
            session.add(incident)
        else:
            incident = session.get(Incident, event["id"])
            if incident:
                incident.ended_at = datetime.fromtimestamp(
                    event["ended_at"], timezone.utc
                ).isoformat()
        session.add(Outbox(id=str(uuid4()), payload={"type": "incident", **event}))
    session.commit()
    if events:
        broadcast("*", {"type": "incidents_changed"})


def process_frame(camera, tracks, fps, latency_ms, jpeg=None):
    now = time.time()
    with Session() as session:
        zones = [
            asdict(z)
            for z in session.scalars(select(Zone).where(Zone.camera_id == camera.id))
        ]
        events = debouncer.update(
            camera.id, now, violations_for(camera.id, tracks, zones)
        )
        apply_events(session, camera, events, jpeg)
    payload = {
        "type": "frame",
        "camera_id": camera.id,
        "timestamp": utcnow(),
        "tracks": tracks,
        "demo": camera.demo,
        "fps": fps,
        "latency_ms": latency_ms,
    }
    live[camera.id] = {**payload, "received": now}
    broadcast(camera.id, payload, jpeg)
    return [event["id"] for event in events if event["action"] == "open"]


async def publish_media():
    if not os.getenv("S3_ENDPOINT"):
        return
    while True:
        try:
            with Session() as session:
                for item in session.scalars(select(MediaOutbox).limit(10)):
                    await asyncio.to_thread(mirror, item.key, item.content_type)
                    session.delete(item)
                session.commit()
        except Exception:
            logger.warning("S3 unavailable; evidence retained locally for retry")
        await asyncio.sleep(5)


async def ticker():
    start = time.monotonic()
    while True:
        try:
            with Session() as session:
                cameras = list(session.scalars(select(Camera)))
            for camera in cameras:
                if camera.enabled and camera.demo and DEMO:
                    process_frame(
                        camera, demo_tracks(camera.id, time.monotonic() - start), 4, 24
                    )
                elif (
                    time.time() - live.get(camera.id, {}).get("received", 0)
                    > debouncer.grace
                ):
                    with Session() as session:
                        apply_events(
                            session,
                            camera,
                            debouncer.update(camera.id, time.time(), {}),
                            None,
                        )
        except Exception:
            logger.exception("Frame processing failed")
        await asyncio.sleep(0.25)


async def publish_outbox():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return
    from redis.asyncio import Redis

    client = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        while True:
            try:
                with Session() as session:
                    events = list(session.scalars(select(Outbox).limit(100)))
                    for event in events:
                        # At-least-once delivery: consumers deduplicate by event_id.
                        await client.xadd(
                            "hse:events",
                            {
                                "event_id": event.id,
                                "payload": json.dumps(event.payload),
                            },
                            maxlen=100000,
                            approximate=True,
                        )
                        session.delete(event)
                    session.commit()
            except Exception:
                logger.warning("Redis unavailable; events retained in SQL outbox")
            await asyncio.sleep(2)
    finally:
        await client.aclose()


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    MEDIA.mkdir(parents=True, exist_ok=True)
    with Session() as session:
        if DEMO:
            seed(session)
        # A restart interrupts track continuity; finalize old intervals explicitly.
        for incident in session.scalars(
            select(Incident).where(Incident.ended_at.is_(None))
        ):
            incident.ended_at = utcnow()
            incident.note = (
                incident.note + "\nИнтервал завершён при перезапуске сервиса."
            ).strip()
        session.commit()
    tasks = [
        asyncio.create_task(ticker()),
        asyncio.create_task(publish_outbox()),
        asyncio.create_task(publish_media()),
    ]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task
    debouncer.states.clear()
    live.clear()


app = FastAPI(
    title="HSE AI-Video",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
app.mount(
    "/api/docs-assets",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="docs-assets",
)
auth = [Depends(authorize)]


@app.get("/api/docs", include_in_schema=False)
def docs():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="HSE AI-Video API",
        swagger_js_url="/api/docs-assets/swagger-ui-bundle.js",
        swagger_css_url="/api/docs-assets/swagger-ui.css",
        swagger_favicon_url="/api/docs-assets/favicon-32x32.png",
        swagger_ui_parameters={"validatorUrl": None},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "demo": DEMO, "version": "0.1.0"}


@app.get("/api/cameras", dependencies=auth)
def cameras_list():
    with Session() as session:
        return [
            camera_dict(c) for c in session.scalars(select(Camera).order_by(Camera.id))
        ]


@app.post("/api/cameras", dependencies=auth, status_code=201)
def camera_add(data: CameraInput):
    if data.source == "demo" and not DEMO:
        raise HTTPException(422, "Демонстрационный режим отключён")
    with Session() as session:
        camera = Camera(
            id="cam-" + uuid4().hex[:8], **data.model_dump(), demo=data.source == "demo"
        )
        session.add(camera)
        session.commit()
        return camera_dict(camera)


@app.patch("/api/cameras/{camera_id}", dependencies=auth)
def camera_toggle(camera_id: str, enabled: bool):
    with Session() as session:
        camera = session.get(Camera, camera_id)
        if not camera:
            raise HTTPException(404, "Камера не найдена")
        camera.enabled = enabled
        session.commit()
        return camera_dict(camera)


@app.get("/api/zones", dependencies=auth)
def zones_list():
    with Session() as session:
        return [asdict(z) for z in session.scalars(select(Zone))]


@app.post("/api/zones", dependencies=auth, status_code=201)
def zone_add(data: ZoneInput):
    with Session() as session:
        if not session.get(Camera, data.camera_id):
            raise HTTPException(404, "Камера не найдена")
        zone = Zone(id="zone-" + uuid4().hex[:8], **data.model_dump())
        session.add(zone)
        session.commit()
        return asdict(zone)


@app.delete("/api/zones/{zone_id}", dependencies=auth)
def zone_delete(zone_id: str):
    with Session() as session:
        zone = session.get(Zone, zone_id)
        if not zone:
            raise HTTPException(404, "Зона не найдена")
        session.delete(zone)
        session.commit()
        return {"deleted": zone_id}


def incident_rows(session, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return list(
        session.scalars(
            select(Incident)
            .where(Incident.started_at >= since)
            .order_by(Incident.started_at.desc())
        )
    )


@app.get("/api/incidents", dependencies=auth)
def incidents_list(
    days: int = Query(default=1, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
):
    with Session() as session:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return [
            asdict(i)
            for i in session.scalars(
                select(Incident)
                .where(Incident.started_at >= since)
                .order_by(Incident.started_at.desc())
                .limit(limit)
            )
        ]


@app.get("/api/incidents/export", dependencies=auth)
def export(days: int = Query(default=1, ge=1, le=90), site: str = "all"):
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "ID",
            "Камера",
            "ID трека",
            "Тип",
            "Время начала UTC",
            "Время окончания UTC",
            "Статус",
            "Уверенность",
            "Демо",
            "Примечание",
        ]
    )

    def safe(value):
        value = str(value or "")
        return (
            "'" + value
            if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
            else value
        )

    with Session() as session:
        selected_ids = {
            c.id
            for c in session.scalars(select(Camera))
            if site == "all" or c.location.split(" · ")[0] == site
        }
        for i in incident_rows(session, days):
            if site != "all" and i.camera_id not in selected_ids:
                continue
            writer.writerow(
                [
                    safe(v)
                    for v in [
                        i.id,
                        i.camera_name,
                        i.track_id,
                        i.kind,
                        i.started_at,
                        i.ended_at,
                        i.status,
                        i.confidence,
                        i.demo,
                        i.note,
                    ]
                ]
            )
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="hse-incidents.csv"'},
    )


@app.patch("/api/incidents/{incident_id}", dependencies=auth)
def incident_update(incident_id: str, data: IncidentUpdate):
    with Session() as session:
        incident = session.get(Incident, incident_id)
        if not incident:
            raise HTTPException(404, "Инцидент не найден")
        incident.status = data.status
        incident.note = data.note
        session.commit()
        return asdict(incident)


@app.get("/api/summary", dependencies=auth)
def summary(days: int = Query(default=1, ge=1, le=90), site: str = "all"):
    with Session() as session:
        cameras = [camera_dict(c) for c in session.scalars(select(Camera))]
        rows = incident_rows(session, days)
    if site != "all":
        cameras = [c for c in cameras if c["location"].split(" · ")[0] == site]
        ids = {c["id"] for c in cameras}
        rows = [i for i in rows if i.camera_id in ids]
    now = datetime.now(timezone.utc)
    series = []
    for ago in reversed(range(12)):
        bucket = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=ago)
        series.append(
            {
                "hour": bucket.isoformat(),
                "count": sum(
                    bucket
                    <= datetime.fromisoformat(i.started_at)
                    < bucket + timedelta(hours=1)
                    for i in rows
                ),
            }
        )
    tracks = [
        t
        for c in cameras
        if c["online"]
        for t in live.get(c["id"], {}).get("tracks", [])
    ]
    known = [
        t for t in tracks if t.get("helmet") is not None and t.get("vest") is not None
    ]
    return {
        "cameras": len(cameras),
        "online": sum(c["online"] for c in cameras),
        "incidents": len(rows),
        "critical": sum(i.severity == "critical" for i in rows),
        "open": sum(i.status != "resolved" for i in rows),
        "compliance": (
            round(100 * sum(t["helmet"] and t["vest"] for t in known) / len(known), 1)
            if known
            else None
        ),
        "checked": len(known),
        "people": len(tracks),
        "series": series,
        "kinds": [
            {"kind": k, "count": n} for k, n in Counter(i.kind for i in rows).items()
        ],
        "demo": DEMO,
    }


@app.get("/api/system", dependencies=auth)
async def system():
    inference = {"status": "unavailable"}
    try:
        import httpx

        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(
                os.getenv("INFERENCE_URL", "http://127.0.0.1:8001") + "/health"
            )
            inference = response.json()
    except Exception:
        pass
    with Session() as session:
        pending = len(list(session.scalars(select(Outbox.id))))
    return {
        "api": "ok",
        "database": engine.dialect.name,
        "demo": DEMO,
        "inference": inference,
        "redis_configured": bool(os.getenv("REDIS_URL")),
        "pending_events": pending,
        "debounce_seconds": debouncer.debounce,
        "close_after_seconds": debouncer.grace,
        "auth_enabled": bool(OPERATOR_TOKEN),
        "version": "0.1.0",
    }


@app.post("/api/validation/image", dependencies=auth)
async def validate_image(frame: UploadFile = File(...), confidence: float = Form(0.35, ge=0.1, le=1)):
    import httpx

    data = await frame.read(3 * 1024 * 1024 + 1)
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(413, "Изображение должно быть не больше 3 МиБ")
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                os.getenv("INFERENCE_URL", "http://127.0.0.1:8001") + "/analyze",
                headers={"X-Service-Token": SERVICE_TOKEN},
                files={"frame": ("frame", data, "application/octet-stream")},
                data={"confidence": str(confidence)},
            )
        result = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Сервис распознавания недоступен. Проверьте его состояние в настройках")
    if response.status_code != 200:
        raise HTTPException(response.status_code if response.status_code in {413,422,429,503} else 502,
                            result.get("detail", "Ошибка распознавания"))
    return result


@app.get("/api/validation/report", dependencies=auth)
def validation_report():
    folder = Path(os.getenv("EVIDENCE_DIR", str(Path(__file__).resolve().parents[1] / "docs" / "evidence")))
    path = folder / "report.json"
    if not path.is_file():
        raise HTTPException(404, "Протокол испытаний пока не опубликован")
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Report too large")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(503, "Не удалось прочитать протокол испытаний")


@app.get("/api/snapshots/{incident_id}", dependencies=auth)
def snapshot(incident_id: str):
    with Session() as session:
        item = session.get(Incident, incident_id)
        if not item or not item.snapshot_url:
            raise HTTPException(404, "Снимок отсутствует")
    path = get_path(f"{item.id}.jpg")
    if not path:
        raise HTTPException(404, "Снимок отсутствует")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/clips/{incident_id}", dependencies=auth)
def clip(incident_id: str):
    with Session() as session:
        item = session.get(Incident, incident_id)
        if not item:
            raise HTTPException(404, "Инцидент не найден")
        # Check the local index before remote access; arbitrary S3 keys are impossible.
        path = MEDIA / f"{item.id}.mp4"
        if not path.is_file():
            raise HTTPException(404, "Видеофрагмент ещё не сохранён или недоступен")
    return FileResponse(path, media_type="video/mp4", filename=f"hse-{item.id}.mp4")


@app.post("/api/internal/clips/{incident_id}", dependencies=[Depends(service_auth)])
async def upload_clip(incident_id: str, clip: UploadFile = File(...)):
    with Session() as session:
        item = session.get(Incident, incident_id)
        if not item or item.demo:
            raise HTTPException(404, "Live incident not found")
        payload = await clip.read(32 * 1024 * 1024 + 1)
        if len(payload) > 32 * 1024 * 1024 or payload[4:8] != b"ftyp":
            raise HTTPException(422, "Expected MP4 under 32 MiB")
        key = f"{item.id}.mp4"
        save_media(key, payload, "video/mp4")
        if os.getenv("S3_ENDPOINT"):
            session.merge(MediaOutbox(key=key, content_type="video/mp4"))
            session.commit()
    return {"saved": True}


@app.get("/api/internal/cameras", dependencies=[Depends(service_auth)])
def internal_cameras():
    with Session() as session:
        return [
            asdict(c)
            for c in session.scalars(
                select(Camera).where(Camera.enabled.is_(True), Camera.demo.is_(False))
            )
        ]


@app.post("/api/internal/frame", dependencies=[Depends(service_auth)])
async def internal_frame(metadata: str = Form(...), frame: UploadFile = File(...)):
    try:
        data = FrameInput.model_validate_json(metadata)
    except ValueError:
        raise HTTPException(422, "Invalid frame metadata")
    jpeg = await frame.read(3 * 1024 * 1024 + 1)
    if len(jpeg) > 3 * 1024 * 1024 or not jpeg.startswith(b"\xff\xd8"):
        raise HTTPException(422, "Expected JPEG under 3 MiB")
    with Session() as session:
        camera = session.get(Camera, data.camera_id)
        if not camera or not camera.enabled or camera.demo:
            raise HTTPException(409, "Camera is not enabled for live ingestion")
    opened = process_frame(
        camera, [t.model_dump() for t in data.tracks], data.fps, data.latency_ms, jpeg
    )
    return {"accepted": True, "capture_clips": opened}


@app.websocket("/api/ws/{camera_id}")
async def websocket(websocket: WebSocket, camera_id: str):
    await websocket.accept()
    queue = asyncio.Queue(maxsize=1)
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        if OPERATOR_TOKEN and not secrets.compare_digest(
            str(message.get("token", "")), OPERATOR_TOKEN
        ):
            await websocket.close(code=4401)
            return
        if camera_id != "*":
            with Session() as session:
                if not session.get(Camera, camera_id):
                    await websocket.close(code=4404)
                    return
        subscribers[camera_id].add(queue)
        while True:
            try:
                payload, jpeg = await asyncio.wait_for(queue.get(), timeout=5)
                await asyncio.wait_for(websocket.send_json(payload), timeout=3)
                if jpeg:
                    await asyncio.wait_for(websocket.send_bytes(jpeg), timeout=3)
            except asyncio.TimeoutError:
                await asyncio.wait_for(
                    websocket.send_json({"type": "heartbeat"}), timeout=3
                )
    except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
        pass
    finally:
        subscribers[camera_id].discard(queue)
