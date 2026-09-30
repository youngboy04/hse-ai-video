"""Optional model export. Requires a separate `pip install ultralytics onnx`.
Downloads only the explicitly selected public weights; no PPE weights are fabricated.
"""

import argparse
import shutil
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detector",
        default="yolo11n.pt",
        help="Use yolo11x.pt for a larger detector, or your own .pt path",
    )
    parser.add_argument("--pose", help="Optional pose weights, e.g. yolov8x-pose.pt")
    args = parser.parse_args()
    from ultralytics import YOLO

    directory = Path(__file__).resolve().parents[1] / "models"
    directory.mkdir(exist_ok=True)
    for weights, name in [(args.detector, "person"), (args.pose, "pose")]:
        if not weights:
            continue
        path = YOLO(weights).export(
            format="onnx",
            imgsz=640,
            batch=1,
            dynamic=False,
            half=False,
            nms=False,
            opset=17,
        )
        destination = directory / f"{name}.onnx"
        if Path(path).resolve() != destination.resolve():
            shutil.copyfile(path, destination)
        print(f"Exported {destination}")
