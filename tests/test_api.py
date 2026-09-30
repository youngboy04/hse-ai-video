import os
import tempfile
from pathlib import Path

_testdir = tempfile.TemporaryDirectory(prefix="hse-api-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_testdir.name) / "test.db")
os.environ["MEDIA_DIR"] = str(Path(_testdir.name) / "media")
os.environ["DEMO_MODE"] = "true"
os.environ["OPERATOR_TOKEN"] = "test-operator"
os.environ["SERVICE_TOKEN"] = "test-service"
os.environ.pop("REDIS_URL", None)
os.environ.pop("S3_ENDPOINT", None)

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import engine


@pytest.fixture(scope="session", autouse=True)
def cleanup_database():
    yield
    engine.dispose()
    _testdir.cleanup()


@pytest.fixture
def client():
    with TestClient(app, headers={"Authorization": "Bearer test-operator"}) as client:
        yield client


def test_auth_and_public_health(client):
    assert client.get("/api/health", headers={"Authorization": ""}).status_code == 200
    assert client.get("/api/cameras", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/internal/cameras").status_code == 401
    assert "/api/docs-assets/swagger-ui-bundle.js" in client.get("/api/docs").text
    assert client.get("/api/docs-assets/swagger-ui.css").status_code == 200


def test_validation_report_and_image_auth(client, monkeypatch, tmp_path):
    monkeypatch.setenv("EVIDENCE_DIR", str(tmp_path))
    assert client.get('/api/validation/report').status_code == 404
    (tmp_path/'report.json').write_text('{"schema_version":1,"purpose":"smoke_test"}')
    assert client.get('/api/validation/report').json()['purpose']=='smoke_test'
    assert client.get('/api/validation/report',headers={'Authorization':''}).status_code==401
    assert client.post('/api/validation/image',headers={'Authorization':''},files={'frame':('image.png',b'x')}).status_code==401
    assert client.post('/api/validation/image',files={'frame':('image.png',b'x'*(3*1024*1024+1))}).status_code==413


def test_validation_proxy_preserves_error_without_exposing_service_key(client, monkeypatch):
    import httpx
    class Upstream:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            assert url.endswith('/analyze')
            assert kwargs['headers']['X-Service-Token']=='test-service'
            return httpx.Response(503,json={'detail':'Модель не установлена'})
    monkeypatch.setattr(httpx,'AsyncClient',Upstream)
    result=client.post('/api/validation/image',files={'frame':('image.png',b'x')})
    assert result.status_code==503
    assert result.json()['detail']=='Модель не установлена'


def test_cameras_and_credential_redaction(client):
    response = client.post(
        "/api/cameras",
        json={
            "name": "RTSP test",
            "location": "Floor 1",
            "source": "rtsp://user:secret@192.168.1.2:554/stream",
        },
    )
    assert response.status_code == 201
    camera = response.json()
    assert "secret" not in response.text and "user" not in response.text
    internal = client.get(
        "/api/internal/cameras", headers={"X-Service-Token": "test-service"}
    ).json()
    assert any(
        c["source"] == "rtsp://user:secret@192.168.1.2:554/stream" for c in internal
    )
    assert (
        client.patch(f"/api/cameras/{camera['id']}?enabled=false").json()["enabled"]
        is False
    )
    assert (
        client.post(
            "/api/cameras",
            json={
                "name": "Unsafe",
                "location": "Floor",
                "source": "file:///etc/passwd",
            },
        ).status_code
        == 422
    )


def test_zone_crud_and_validation(client):
    body = {
        "camera_id": "cam-01",
        "name": "Test zone",
        "points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
    }
    zone = client.post("/api/zones", json=body)
    assert zone.status_code == 201
    assert client.delete("/api/zones/" + zone.json()["id"]).status_code == 200
    assert client.delete("/api/zones/" + zone.json()["id"]).status_code == 404
    body["points"] = [[0, 0], [1, 1], [0, 1], [1, 0]]
    assert client.post("/api/zones", json=body).status_code == 422
    body["points"] = [[0, 0], [1, 0], [0, 1]]
    body["camera_id"] = "missing"
    assert client.post("/api/zones", json=body).status_code == 404


def test_incident_workflow_csv_and_persistence(client):
    incident = client.get("/api/incidents").json()[0]
    url = "/api/incidents/" + incident["id"]
    assert (
        client.patch(
            url, json={"status": "acknowledged", "note": "=UNSAFE()"}
        ).status_code
        == 200
    )
    assert (
        client.patch(url, json={"status": "resolved", "note": "=UNSAFE()"}).json()[
            "status"
        ]
        == "resolved"
    )
    rows = client.get("/api/incidents").json()
    assert next(i for i in rows if i["id"] == incident["id"])["status"] == "resolved"
    export = client.get("/api/incidents/export")
    assert export.status_code == 200 and "'=UNSAFE()" in export.text
    assert "text/csv" in export.headers["content-type"]
    assert client.patch(url, json={"status": "invalid"}).status_code == 422


def test_summary_and_limits(client):
    s = client.get("/api/summary").json()
    assert s["cameras"] >= 4 and len(s["series"]) == 12
    assert s["incidents"] >= 47
    assert client.get("/api/incidents?days=-1").status_code == 422
    assert client.get("/api/incidents?limit=100000").status_code == 422


def test_stream_requires_auth_and_sends_tracks(client):
    with client.websocket_connect("/api/ws/cam-01") as ws:
        ws.send_json({"token": "test-operator"})
        frame = ws.receive_json()
        assert frame["type"] == "frame" and frame["camera_id"] == "cam-01"
        assert len(frame["tracks"]) == 3 and frame["demo"] is True
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/ws/cam-01") as ws:
            ws.send_json({"token": "wrong"})
            ws.receive_json()
    assert exc.value.code == 4401


def test_frame_ingestion_and_evidence(client, monkeypatch):
    import json

    live = client.post(
        "/api/cameras",
        json={
            "name": "Live test",
            "location": "Floor",
            "source": "rtsp://192.168.1.2/live",
        },
    ).json()
    meta = {
        "camera_id": live["id"],
        "tracks": [
            {
                "id": 1,
                "bbox": [0.1, 0.1, 0.3, 0.6],
                "confidence": 0.9,
                "helmet": None,
                "vest": None,
            }
        ],
        "fps": 5,
        "latency_ms": 30,
    }
    assert (
        client.post(
            "/api/internal/frame",
            headers={"X-Service-Token": "test-service"},
            data={"metadata": json.dumps(meta)},
            files={"frame": ("frame.jpg", b"not-jpeg", "image/jpeg")},
        ).status_code
        == 422
    )
    assert client.get("/api/snapshots/nonexistent").status_code == 404
    assert client.get("/api/clips/nonexistent").status_code == 404
    from backend.main import debouncer

    monkeypatch.setattr(debouncer, "debounce", 0)
    meta["tracks"][0]["helmet"] = False
    # Upload a real, small JPEG and ensure the same bytes are available as evidence.
    import io

    Image = pytest.importorskip("PIL.Image")
    jpeg = io.BytesIO()
    Image.new("RGB", (64, 48), (20, 80, 100)).save(jpeg, format="JPEG")
    accepted = client.post(
        "/api/internal/frame",
        headers={"X-Service-Token": "test-service"},
        data={"metadata": json.dumps(meta)},
        files={"frame": ("frame.jpg", jpeg.getvalue(), "image/jpeg")},
    )
    assert accepted.status_code == 200
    incident_id = accepted.json()["capture_clips"][0]
    snapshot = client.get("/api/snapshots/" + incident_id)
    assert snapshot.content == jpeg.getvalue()
    assert (
        client.get(
            "/api/snapshots/" + incident_id, headers={"Authorization": ""}
        ).status_code
        == 401
    )
    if __import__("importlib").util.find_spec("av"):
        from ingestion.main import encode_clip

        video = encode_clip([(jpeg.getvalue(), float(i) / 5) for i in range(6)])
        upload = client.post(
            "/api/internal/clips/" + incident_id,
            headers={"X-Service-Token": "test-service"},
            files={"clip": ("clip.mp4", video, "video/mp4")},
        )
        assert upload.status_code == 200
        assert client.get("/api/clips/" + incident_id).content == video
