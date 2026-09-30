"""Time-based debounce and incident aggregation, independent of frame rate."""

from dataclasses import dataclass
from uuid import uuid4


def inside_polygon(point, polygon):
    x, y = point
    inside = False
    for i, (ax, ay) in enumerate(polygon):
        bx, by = polygon[i - 1]
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if (
            abs(cross) < 1e-9
            and min(ax, bx) <= x <= max(ax, bx)
            and min(ay, by) <= y <= max(ay, by)
        ):
            return True
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside


@dataclass
class Trigger:
    first: float
    last: float
    incident_id: str | None = None
    confidence: float = 0
    metadata: dict | None = None


class DebounceEngine:
    def __init__(self, debounce=2.0, grace=3.0):
        self.debounce = debounce
        self.grace = grace
        self.states: dict[tuple, Trigger] = {}

    def update(self, camera_id: str, now: float, violations: dict[tuple, dict]):
        events = []
        # Expire before processing so a large frame gap cannot qualify as continuity.
        for key, state in list(self.states.items()):
            if key[0] != camera_id:
                continue
            if now - state.last > self.grace:
                if state.incident_id:
                    events.append(
                        {
                            "action": "close",
                            "id": state.incident_id,
                            "ended_at": state.last,
                        }
                    )
                del self.states[key]
            elif key not in violations and not state.incident_id:
                del self.states[key]
        for key, meta in violations.items():
            state = self.states.setdefault(key, Trigger(now, now, metadata=meta))
            state.last = now
            state.confidence = max(state.confidence, meta["confidence"])
            if state.incident_id is None and now - state.first >= self.debounce:
                state.incident_id = str(uuid4())
                events.append(
                    {
                        "action": "open",
                        "id": state.incident_id,
                        "started_at": state.first,
                        "confidence": state.confidence,
                        **meta,
                    }
                )
        return events


def violations_for(camera_id, tracks, zones):
    violations = {}
    for track in tracks:
        common = {
            "track_id": track["id"],
            "confidence": track["confidence"],
            "camera_id": camera_id,
            "zone_name": "",
        }
        for attr, kind in [("helmet", "no_helmet"), ("vest", "no_vest")]:
            if track.get(attr) is False:
                violations[(camera_id, track["id"], kind, "")] = {
                    **common,
                    "kind": kind,
                }
        if track.get("fall") is True:
            violations[(camera_id, track["id"], "fall", "")] = {
                **common,
                "kind": "fall",
            }
        x1, _, x2, y2 = track["bbox"]
        for zone in zones:
            if zone["enabled"] and inside_polygon(((x1 + x2) / 2, y2), zone["points"]):
                violations[(camera_id, track["id"], "zone", zone["id"])] = {
                    **common,
                    "kind": "zone",
                    "zone_name": zone["name"],
                }
    return violations
