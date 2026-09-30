import asyncio
import io
import os
import secrets
import time
import hashlib
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends
from PIL import Image, ImageOps, UnidentifiedImageError
from .pipeline import Pipeline

pipeline = None
lock = asyncio.Lock()
Image.MAX_IMAGE_PIXELS = 20_000_000


@asynccontextmanager
async def lifespan(app):
    global pipeline
    pipeline = await asyncio.to_thread(Pipeline)
    yield


app = FastAPI(title="HSE Inference", lifespan=lifespan)


def auth(x_service_token: str | None = Header(default=None)):
    if not secrets.compare_digest(
        x_service_token or "", os.getenv("SERVICE_TOKEN", "local-development-change-me")
    ):
        raise HTTPException(401, "Invalid service token")


@app.get("/health")
def health():
    return {
        "status": (
            "ready" if pipeline and pipeline.models["detector"] else "awaiting_models"
        ),
        "provider": pipeline.provider if pipeline else None,
        "models": (
            {name: model is not None for name, model in pipeline.models.items()}
            if pipeline
            else {}
        ),
        "model_info": pipeline.model_info if pipeline else {},
    }


@app.post("/analyze", dependencies=[Depends(auth)])
async def analyze(frame: UploadFile = File(...), confidence: float = Form(0.35, ge=0.1, le=1)):
    """Stateless person detection. Does not create tracks or operational incidents."""
    if pipeline is None or pipeline.models["detector"] is None:
        raise HTTPException(503, "Модель обнаружения людей не установлена")
    data = await frame.read(3 * 1024 * 1024 + 1)
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(413, "Изображение должно быть не больше 3 МиБ")
    try:
        source = Image.open(io.BytesIO(data))
        if source.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Unsupported image format")
        if source.width * source.height > 20_000_000:
            raise ValueError("Image exceeds pixel limit")
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGB")
    except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "Ожидается изображение JPEG, PNG или WebP до 20 мегапикселей")
    if image.width * image.height > 20_000_000:
        raise HTTPException(422, "Изображение превышает 20 мегапикселей")
    try:
        await asyncio.wait_for(lock.acquire(), timeout=2)
    except asyncio.TimeoutError:
        raise HTTPException(429, "Сервис занят. Повторите проверку")
    try:
        started = time.perf_counter()
        boxes, scores = await asyncio.to_thread(pipeline.detect, image)
        elapsed = (time.perf_counter() - started) * 1000
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc))
    finally:
        lock.release()
    return {
        "scope": "person_detection", "synthetic": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image_sha256": hashlib.sha256(data).hexdigest(),
        "width": image.width, "height": image.height,
        "confidence_threshold": confidence,
        "latency_ms": round(elapsed, 2), "provider": pipeline.provider,
        "model": pipeline.model_info["detector"],
        "detections": [
            {"bbox": [float(b[0])/image.width, float(b[1])/image.height, float(b[2])/image.width, float(b[3])/image.height], "confidence": float(s), "class": "person"}
            for b, s in zip(boxes, scores) if s >= confidence
        ],
        "limitations": ["Проверяется обнаружение людей на одном изображении", "СИЗ, падения и качество трекинга этой проверкой не оцениваются", "Уверенность детектора не является измеренной точностью"],
    }


@app.post("/infer", dependencies=[Depends(auth)])
async def infer(
    camera_id: str = Form(..., max_length=100), frame: UploadFile = File(...)
):
    if pipeline is None or pipeline.models["detector"] is None:
        raise HTTPException(503, "Install detector model; see README model contracts")
    data = await frame.read(3 * 1024 * 1024 + 1)
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(413, "Frame exceeds 3 MiB")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        image = image.convert("RGB")
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(422, "Invalid image")
    start = time.perf_counter()
    try:
        await asyncio.wait_for(lock.acquire(), timeout=2)
    except asyncio.TimeoutError:
        raise HTTPException(429, "Inference busy; drop frame")
    try:
        tracks = await asyncio.to_thread(pipeline.infer, image, camera_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc))
    finally:
        lock.release()
    return {
        "tracks": tracks,
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
    }
