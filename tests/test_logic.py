import pytest
from backend.logic import DebounceEngine, inside_polygon, violations_for
from backend.schemas import ZoneInput, CameraInput, TrackInput


def violation(camera="cam-1", track=12, kind="no_helmet"):
    return {
        (camera, track, kind, ""): {
            "camera_id": camera,
            "track_id": track,
            "kind": kind,
            "zone_name": "",
            "confidence": 0.91,
        }
    }


def test_debounce_is_time_based_and_aggregates():
    engine = DebounceEngine(debounce=2, grace=3)
    assert engine.update("cam-1", 0, violation()) == []
    assert engine.update("cam-1", 1.9, violation()) == []
    opened = engine.update("cam-1", 2, violation())
    assert len(opened) == 1 and opened[0]["action"] == "open"
    assert engine.update("cam-1", 3, violation()) == []
    assert engine.update("cam-1", 5, {}) == []
    closed = engine.update("cam-1", 6.1, {})
    assert closed == [{"action": "close", "id": opened[0]["id"], "ended_at": 3}]


def test_single_false_frame_resets_unconfirmed_violation():
    engine = DebounceEngine()
    engine.update("cam-1", 0, violation())
    engine.update("cam-1", 1.5, {})
    assert not engine.update("cam-1", 2, violation())
    assert not engine.update("cam-1", 3.9, violation())
    assert engine.update("cam-1", 4, violation())[0]["action"] == "open"


def test_missing_frames_cannot_confirm_violation():
    engine = DebounceEngine()
    engine.update("cam-1", 0, violation())
    assert not engine.update("cam-1", 100, violation())


def test_tracks_are_scoped_to_camera():
    engine = DebounceEngine()
    engine.update("cam-1", 0, violation())
    engine.update("cam-2", 1, violation("cam-2"))
    assert len(engine.update("cam-1", 2, violation())) == 1
    assert not engine.update("cam-2", 2, violation("cam-2"))
    assert len(engine.update("cam-2", 3, violation("cam-2"))) == 1


def test_reentry_creates_new_incident_after_gap():
    engine = DebounceEngine()
    engine.update("cam-1", 0, violation())
    first = engine.update("cam-1", 2, violation())[0]
    events = engine.update("cam-1", 10, violation())
    assert len(events) == 1 and events[0]["action"] == "close"
    second = engine.update("cam-1", 12, violation())[0]
    assert first["id"] != second["id"]


@pytest.mark.parametrize(
    "point,expected",
    [
        ((0.1, 0.1), True),
        ((0, 0), True),
        ((1, 0.5), True),
        ((1.1, 0.5), False),
        ((-0.1, 0.5), False),
    ],
)
def test_polygon_and_boundary(point, expected):
    assert inside_polygon(point, [(0, 0), (1, 0), (1, 1), (0, 1)]) is expected


def test_concave_polygon():
    polygon = [(0, 0), (1, 0), (1, 0.3), (0.3, 0.3), (0.3, 1), (0, 1)]
    assert inside_polygon((0.2, 0.8), polygon)
    assert not inside_polygon((0.8, 0.8), polygon)


def test_unknown_ppe_never_becomes_violation():
    track = {
        "id": 1,
        "bbox": [0.1, 0.1, 0.2, 0.4],
        "confidence": 0.9,
        "helmet": None,
        "vest": None,
    }
    assert violations_for("cam-1", [track], []) == {}


def test_geofence_uses_feet_not_box_center():
    zone = {
        "id": "z",
        "enabled": True,
        "name": "Press",
        "points": [(0, 0.7), (1, 0.7), (1, 1), (0, 1)],
    }
    track = {"id": 1, "bbox": [0.1, 0.1, 0.2, 0.9], "confidence": 0.9}
    assert ("cam-1", 1, "zone", "z") in violations_for("cam-1", [track], [zone])


@pytest.mark.parametrize(
    "points",
    [
        [[0, 0], [1, 1], [0, 1], [1, 0]],
        [[0, 0], [0.5, 0.5], [1, 1]],
        [[0, 0], [0, 0], [1, 1]],
        [[0, 0], [1, 0], [2, 1]],
        [[0, 0], [1, 0], [float("nan"), 1]],
    ],
)
def test_reject_invalid_zones(points):
    with pytest.raises(ValueError):
        ZoneInput(camera_id="1", name="zone", points=points)


def test_reject_file_source_and_inverted_box():
    with pytest.raises(ValueError):
        CameraInput(name="cam", location="floor", source="file:///etc/passwd")
    with pytest.raises(ValueError):
        TrackInput(id=1, bbox=[0.7, 0.2, 0.1, 0.9], confidence=0.9)
