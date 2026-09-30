"""One decoder thread and latest-frame buffer per camera; async inference consumers."""

import asyncio
import io
import logging
import os
import queue
import threading
import time
from collections import deque
from contextlib import suppress

import av
import httpx
from PIL import Image

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hse.ingestion")
BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
INFERENCE = os.getenv("INFERENCE_URL", "http://127.0.0.1:8001")
HEADERS = {"X-Service-Token": os.getenv("SERVICE_TOKEN", "local-development-change-me")}
TARGET_FPS = float(os.getenv("INFERENCE_FPS", "8"))


class CameraWorker:
    def __init__(self, camera):
        self.camera = camera
        self.frames = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.sample_interval = 1 / TARGET_FPS
        self.history = deque(maxlen=160)
        self.history_lock = threading.Lock()
        self.clips = set()
        self.observations = deque(maxlen=30)
        self.thread = threading.Thread(
            target=self.decode, daemon=True, name=f"decoder-{camera['id']}"
        )

    def decode(self):
        backoff = 1
        while not self.stop.is_set():
            try:
                with av.open(
                    self.camera["source"],
                    timeout=(5, 5),
                    options={"rtsp_transport": "tcp", "fflags": "nobuffer"},
                ) as container:
                    stream = container.streams.video[0]
                    stream.thread_type = "AUTO"
                    last = 0
                    backoff = 1
                    for decoded in container.decode(stream):
                        if self.stop.is_set():
                            return
                        now = time.monotonic()
                        if now - last < self.sample_interval:
                            continue
                        last = now
                        image = decoded.to_image()
                        image.thumbnail((1280, 720))
                        buf = io.BytesIO()
                        image.save(buf, format="JPEG", quality=80)
                        with self.history_lock:
                            self.history.append((buf.getvalue(), now))
                        with suppress(queue.Empty):
                            self.frames.get_nowait()
                        with suppress(queue.Full):
                            self.frames.put_nowait((buf.getvalue(), now))
                self.stop.wait(backoff)
            except Exception:
                # Never log the RTSP URL or camera credentials.
                log.warning(
                    "Camera %s disconnected; retry in %ss", self.camera["id"], backoff
                )
                self.stop.wait(backoff)
                backoff = min(backoff * 2, 30)

    async def consume(self):
        self.thread.start()
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            try:
                while True:
                    try:
                        frame, captured = self.frames.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(0.025)
                        continue
                    if time.monotonic() - captured > 2:
                        continue
                    start = time.monotonic()
                    try:
                        response = await client.post(
                            INFERENCE + "/infer",
                            data={"camera_id": self.camera["id"]},
                            files={"frame": ("frame.jpg", frame, "image/jpeg")},
                        )
                        response.raise_for_status()
                        result = response.json()
                        elapsed = time.monotonic() - start
                        self.sample_interval = min(
                            2, max(1 / TARGET_FPS, elapsed * 1.1)
                        )
                        if time.monotonic() - captured > 3:
                            continue
                        import json

                        processed = time.monotonic()
                        if self.observations and processed - self.observations[-1] > 8:
                            self.observations.clear()
                        self.observations.append(processed)
                        observed_fps = (
                            (len(self.observations) - 1)
                            / max(0.001, processed - self.observations[0])
                            if len(self.observations) > 1
                            else 0
                        )
                        metadata = {
                            "camera_id": self.camera["id"],
                            "tracks": result["tracks"],
                            "latency_ms": (processed - captured) * 1000,
                            "fps": min(120, observed_fps),
                        }
                        response = await client.post(
                            BACKEND + "/api/internal/frame",
                            data={"metadata": json.dumps(metadata)},
                            files={"frame": ("frame.jpg", frame, "image/jpeg")},
                        )
                        response.raise_for_status()
                        for incident_id in response.json().get("capture_clips", []):
                            task = asyncio.create_task(
                                self.capture_clip(incident_id, time.monotonic())
                            )
                            self.clips.add(task)
                            task.add_done_callback(self.clips.discard)
                    except (httpx.HTTPError, ValueError, KeyError):
                        log.warning(
                            "Analysis unavailable for camera %s; dropping frame",
                            self.camera["id"],
                        )
                        self.sample_interval = min(2, self.sample_interval * 1.5)
                        await asyncio.sleep(1)
            finally:
                self.stop.set()
                for task in self.clips:
                    task.cancel()
                await asyncio.gather(*self.clips, return_exceptions=True)
                await asyncio.to_thread(self.thread.join, 6)

    async def capture_clip(self, incident_id, event_time):
        # Five seconds before + five after, sampled stream; never claim full camera FPS.
        await asyncio.sleep(5)
        with self.history_lock:
            frames = [
                (data, ts)
                for data, ts in self.history
                if event_time - 5 <= ts <= event_time + 5
            ]
        if len(frames) < 2:
            return
        try:
            data = await asyncio.to_thread(encode_clip, frames)
            async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
                response = await client.post(
                    BACKEND + f"/api/internal/clips/{incident_id}",
                    files={"clip": ("clip.mp4", data, "video/mp4")},
                )
                response.raise_for_status()
        except Exception:
            log.warning("Clip could not be saved for incident %s", incident_id)


def encode_clip(frames):
    from fractions import Fraction

    output = io.BytesIO()
    with av.open(
        output, mode="w", format="mp4", options={"movflags": "frag_keyframe+empty_moov"}
    ) as container:
        stream = container.add_stream("libx264", rate=10)
        sample = Image.open(io.BytesIO(frames[0][0]))
        width, height = sample.size
        stream.width = width - width % 2
        stream.height = height - height % 2
        stream.pix_fmt = "yuv420p"
        stream.options = {"preset": "ultrafast", "crf": "28"}
        stream.time_base = Fraction(1, 1000)
        for data, ts in frames:
            image = (
                Image.open(io.BytesIO(data))
                .convert("RGB")
                .resize((stream.width, stream.height))
            )
            frame = av.VideoFrame.from_image(image)
            frame.pts = round((ts - frames[0][1]) * 1000)
            frame.time_base = Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return output.getvalue()


async def main():
    workers = {}
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        try:
            while True:
                try:
                    response = await client.get(BACKEND + "/api/internal/cameras")
                    response.raise_for_status()
                    cameras = {c["id"]: c for c in response.json()}
                    for key in list(workers):
                        if (
                            key not in cameras
                            or workers[key][0].camera["source"]
                            != cameras[key]["source"]
                            or workers[key][1].done()
                        ):
                            worker, task = workers.pop(key)
                            worker.stop.set()
                            task.cancel()
                            with suppress(asyncio.CancelledError):
                                await task
                    for key, camera in cameras.items():
                        if key not in workers:
                            worker = CameraWorker(camera)
                            workers[key] = (
                                worker,
                                asyncio.create_task(worker.consume()),
                            )
                except (httpx.HTTPError, ValueError):
                    log.warning("Waiting for backend configuration")
                await asyncio.sleep(5)
        finally:
            for worker, task in workers.values():
                worker.stop.set()
                task.cancel()
            await asyncio.gather(
                *(task for _, task in workers.values()), return_exceptions=True
            )


if __name__ == "__main__":
    asyncio.run(main())
