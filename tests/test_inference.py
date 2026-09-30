import numpy as np
import pytest

onnx = pytest.importorskip("onnx")
pytest.importorskip("supervision")
from PIL import Image
from inference.pipeline import Pipeline, nms


def export_constant(path, input_shape, output):
    # Contract fixture, deliberately not a trained detection model.
    from onnx import helper, numpy_helper, TensorProto

    graph = helper.make_graph(
        [
            helper.make_node(
                "Constant", [], ["output"], value=numpy_helper.from_array(output)
            )
        ],
        "fixture",
        [helper.make_tensor_value_info("images", TensorProto.FLOAT, input_shape)],
        [
            helper.make_tensor_value_info(
                "output", TensorProto.FLOAT, list(output.shape)
            )
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.save(model, str(path))


def test_real_onnx_execution_and_bytetrack(tmp_path, monkeypatch):
    detector = np.zeros((1, 84, 2), dtype=np.float32)
    detector[0, :4, 0] = [320, 320, 100, 300]
    detector[0, 4, 0] = 0.96
    detector[0, :4, 1] = [321, 321, 100, 300]
    detector[0, 4, 1] = 0.8
    export_constant(tmp_path / "person.onnx", [1, 3, 640, 640], detector)
    export_constant(
        tmp_path / "ppe.onnx",
        [1, 3, 224, 224],
        np.asarray([[0.03, 0.98]], dtype=np.float32),
    )
    monkeypatch.setenv("DETECTOR_MODEL", str(tmp_path / "person.onnx"))
    monkeypatch.setenv("PPE_MODEL", str(tmp_path / "ppe.onnx"))
    monkeypatch.setenv("POSE_MODEL", str(tmp_path / "missing.onnx"))
    monkeypatch.setenv("BEHAVIOR_MODEL", str(tmp_path / "missing.onnx"))
    pipeline = Pipeline()
    image = Image.new("RGB", (1280, 720))
    first = pipeline.infer(image, "camera-a")
    second = pipeline.infer(image, "camera-a")
    assert len(first) == len(second) == 1
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["helmet"] is False and first[0]["vest"] is True
    assert first[0]["fall"] is None
    assert first[0]["bbox"] == pytest.approx(
        [0.421875, 0.0833333, 0.578125, 0.9166667], abs=0.0001
    )


def test_no_weights_do_not_fake_detections(tmp_path, monkeypatch):
    monkeypatch.setenv("DETECTOR_MODEL", str(tmp_path / "missing.onnx"))
    monkeypatch.setenv("PPE_MODEL", str(tmp_path / "missing.onnx"))
    pipeline = Pipeline()
    with pytest.raises(RuntimeError, match="not installed"):
        pipeline.infer(Image.new("RGB", (640, 640)), "camera-a")


def test_nms_preserves_separate_people():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [30, 30, 40, 40]], dtype=float)
    assert nms(boxes, np.asarray([0.9, 0.8, 0.7])).tolist() == [0, 2]


def test_yolo_pose_adapter_and_temporal_cascade(tmp_path, monkeypatch):
    detector = np.zeros((1, 84, 1), dtype=np.float32)
    detector[0, :4, 0] = [320, 320, 200, 400]
    detector[0, 4, 0] = 0.98
    pose = np.zeros((1, 56, 1), dtype=np.float32)
    pose[0, 4, 0] = 0.99
    pose[0, 5:, 0] = np.tile([320, 320, 0.95], 17)
    export_constant(tmp_path / "person.onnx", [1, 3, 640, 640], detector)
    export_constant(tmp_path / "pose.onnx", [1, 3, 640, 640], pose)
    export_constant(
        tmp_path / "behavior.onnx",
        [1, 3, 30, 17, 1],
        np.array([[0.02, 0.98]], dtype=np.float32),
    )
    for key, name in [
        ("DETECTOR_MODEL", "person"),
        ("POSE_MODEL", "pose"),
        ("BEHAVIOR_MODEL", "behavior"),
        ("PPE_MODEL", "missing"),
    ]:
        monkeypatch.setenv(key, str(tmp_path / f"{name}.onnx"))
    pipeline = Pipeline()
    image = Image.new("RGB", (640, 640))
    for _ in range(29):
        tracks = pipeline.infer(image, "camera-a")
        assert tracks[0]["fall"] is None
    final = pipeline.infer(image, "camera-a")[0]
    assert final["fall"] is True
    assert len(final["pose"]) == 17
    assert final["pose"][0] == pytest.approx([0.5, 0.5, 0.95])
    assert final["helmet"] is None
