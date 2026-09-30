"""YOLO ONNX person detection -> ByteTrack -> optional PPE and pose/ST-GCN heads.

Model contracts and limitations are specified in README. Missing weights never
produce fabricated detections. A PPE classifier is required for PPE decisions.
"""

import os
import hashlib
import time
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import onnxruntime as ort
import supervision as sv
from PIL import Image


def tensor(image, size):
    return (
        np.asarray(image.resize(size), dtype=np.float32).transpose(2, 0, 1)[None]
        / 255.0
    )


def nms(boxes, scores, threshold=0.5):
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        if len(order) == 1:
            break
        others = order[1:]
        a = np.maximum(boxes[i, :2], boxes[others, :2])
        b = np.minimum(boxes[i, 2:], boxes[others, 2:])
        intersection = np.maximum(b - a, 0).prod(axis=1)
        area = np.maximum(boxes[:, 2:] - boxes[:, :2], 0).prod(axis=1)
        iou = intersection / np.maximum(area[i] + area[others] - intersection, 1e-8)
        order = others[iou < threshold]
    return np.asarray(keep, dtype=int)


class Pipeline:
    def __init__(self):
        self.provider = os.getenv("ONNX_PROVIDER", "CPUExecutionProvider")
        if self.provider not in ort.get_available_providers():
            raise RuntimeError(
                f"Requested ONNX provider is unavailable: {self.provider}"
            )
        self.models = {}
        self.model_info = {}
        for name, env, default in [
            ("detector", "DETECTOR_MODEL", "/models/person.onnx"),
            ("ppe", "PPE_MODEL", "/models/ppe.onnx"),
            ("pose", "POSE_MODEL", "/models/pose.onnx"),
            ("behavior", "BEHAVIOR_MODEL", "/models/behavior.onnx"),
        ]:
            path = Path(os.getenv(env, default))
            self.models[name] = (
                ort.InferenceSession(str(path), providers=[self.provider])
                if path.is_file()
                else None
            )
            self.model_info[name] = None
            if self.models[name] is not None:
                with path.open("rb") as stream:
                    self.model_info[name] = {"file": path.name, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
        self.trackers = {}
        self.last_seen = {}
        self.history = defaultdict(lambda: deque(maxlen=30))
        self.history_seen = {}
        self.max_streams = int(os.getenv("MAX_STREAMS", "64"))
        self.frame_rate = int(os.getenv("INFERENCE_FPS", "8"))

    def run(self, name, value):
        session = self.models[name]
        return session.run(None, {session.get_inputs()[0].name: value})[0]

    def detect(self, image):
        size = 640
        width, height = image.size
        scale = min(size / width, size / height)
        resized = image.resize((round(width * scale), round(height * scale)))
        left = (size - resized.width) // 2
        top = (size - resized.height) // 2
        padded = Image.new("RGB", (size, size), (114, 114, 114))
        padded.paste(resized, (left, top))
        raw = np.asarray(self.run("detector", tensor(padded, (size, size))))
        if raw.ndim != 3 or raw.shape[0] != 1:
            raise ValueError("Detector must output [1, 4+classes, anchors]")
        predictions = raw[0].T
        if predictions.shape[1] < 5 or predictions.shape[1] > 512:
            raise ValueError(
                "Unsupported detector export; use YOLO raw output, nms=False"
            )
        classes = predictions[:, 4:].argmax(axis=1)
        scores = predictions[:, 4:].max(axis=1)
        valid = (classes == int(os.getenv("PERSON_CLASS_ID", "0"))) & (scores >= 0.1)
        centers = predictions[valid, :4]
        scores = scores[valid]
        boxes = np.column_stack(
            (centers[:, :2] - centers[:, 2:] / 2, centers[:, :2] + centers[:, 2:] / 2)
        )
        boxes[:, [0, 2]] = (boxes[:, [0, 2]] - left) / scale
        boxes[:, [1, 3]] = (boxes[:, [1, 3]] - top) / scale
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, width)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, height)
        valid = (boxes[:, 2] - boxes[:, 0] > 2) & (boxes[:, 3] - boxes[:, 1] > 2)
        boxes = boxes[valid]
        scores = scores[valid]
        keep = nms(boxes, scores)
        return boxes[keep], scores[keep]

    def estimate_pose(self, crop):
        shape = self.models["pose"].get_inputs()[0].shape
        height = shape[-2] if isinstance(shape[-2], int) else 640
        width = shape[-1] if isinstance(shape[-1], int) else 640
        output = np.asarray(self.run("pose", tensor(crop, (width, height))))
        if output.shape == (1, 17, 3):
            pose = output[0]
        elif output.ndim == 3 and output.shape[0] == 1 and output.shape[1] == 56:
            # Raw YOLOv8-pose: xywh, person confidence, 17*(x,y,confidence).
            candidates = output[0].T
            best = candidates[candidates[:, 4].argmax()]
            pose = best[5:].reshape(17, 3).copy()
            pose[:, 0] /= width
            pose[:, 1] /= height
            pose = np.clip(pose, 0, 1)
            if best[4] < 0.3:
                pose[:, 2] = 0
        else:
            raise ValueError("Pose output must be [1,17,3] or YOLOv8-pose [1,56,N]")
        if not np.isfinite(pose).all() or (pose < 0).any() or (pose > 1).any():
            raise ValueError("Pose keypoints and confidence must lie in [0,1]")
        return pose

    def infer(self, image, camera_id):
        if self.models["detector"] is None:
            raise RuntimeError("Person detector weights are not installed")
        now = time.monotonic()
        for key, last in list(self.last_seen.items()):
            if now - last > 60:
                self.trackers.pop(key, None)
                self.last_seen.pop(key, None)
        for key, last in list(self.history_seen.items()):
            if now - last > 10:
                self.history.pop(key, None)
                self.history_seen.pop(key, None)
        if camera_id not in self.trackers:
            if len(self.trackers) >= self.max_streams:
                raise RuntimeError("Maximum stream count reached")
            self.trackers[camera_id] = sv.ByteTrack(
                track_activation_threshold=0.35,
                lost_track_buffer=30,
                frame_rate=self.frame_rate,
            )
        # Camera disconnect must break identity and temporal continuity.
        elif now - self.last_seen.get(camera_id, now) > 3:
            self.trackers[camera_id] = sv.ByteTrack(
                track_activation_threshold=0.35,
                lost_track_buffer=30,
                frame_rate=self.frame_rate,
            )
            for key in [k for k in self.history if k[0] == camera_id]:
                self.history.pop(key, None)
                self.history_seen.pop(key, None)
        self.last_seen[camera_id] = now
        boxes, scores = self.detect(image)
        detections = self.trackers[camera_id].update_with_detections(
            sv.Detections(
                xyxy=boxes, confidence=scores, class_id=np.zeros(len(scores), dtype=int)
            )
        )
        width, height = image.size
        result = []
        for box, confidence, track_id in zip(
            detections.xyxy, detections.confidence, detections.tracker_id
        ):
            x1, y1, x2, y2 = box.tolist()
            crop = image.crop((int(x1), int(y1), int(x2), int(y2)))
            item = {
                "id": int(track_id),
                "bbox": [x1 / width, y1 / height, x2 / width, y2 / height],
                "confidence": float(confidence),
                "helmet": None,
                "vest": None,
                "fall": None,
            }
            if self.models["ppe"]:
                # Independent probability outputs, never infer absence from missing detections.
                probabilities = np.asarray(
                    self.run("ppe", tensor(crop, (224, 224)))
                ).reshape(-1)
                if (
                    probabilities.size != 2
                    or not np.isfinite(probabilities).all()
                    or (probabilities < 0).any()
                    or (probabilities > 1).any()
                ):
                    raise ValueError(
                        "PPE output must be two probabilities [helmet, vest]"
                    )
                for attr, p in zip(("helmet", "vest"), probabilities):
                    item[attr] = True if p >= 0.8 else False if p <= 0.2 else None
            if self.models["pose"]:
                pose = self.estimate_pose(crop)
                global_pose = pose.copy()
                global_pose[:, 0] = (x1 + pose[:, 0] * (x2 - x1)) / width
                global_pose[:, 1] = (y1 + pose[:, 1] * (y2 - y1)) / height
                item["pose"] = global_pose.tolist()
                key = (camera_id, int(track_id))
                if now - self.history_seen.get(key, now) > max(
                    0.75, 2 / self.frame_rate
                ):
                    self.history[key].clear()
                self.history[key].append(global_pose)
                self.history_seen[key] = now
                if self.models["behavior"] and len(self.history[key]) == 30:
                    graph = np.asarray(self.history[key], dtype=np.float32).transpose(
                        2, 0, 1
                    )[None, :, :, :, None]
                    scores = np.asarray(self.run("behavior", graph)).reshape(-1)
                    if (
                        scores.size != 2
                        or not np.isfinite(scores).all()
                        or (scores < 0).any()
                        or (scores > 1).any()
                    ):
                        raise ValueError(
                            "Behavior output must be [normal, fall] probabilities"
                        )
                    item["fall"] = bool(scores[1] >= 0.9)
            result.append(item)
        return result
