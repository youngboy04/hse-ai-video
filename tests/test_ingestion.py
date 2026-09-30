import io
import pytest

av = pytest.importorskip("av")
from PIL import Image
from ingestion.main import encode_clip


def test_clip_is_decodable_and_preserves_elapsed_time():
    frames = []
    for index in range(12):
        out = io.BytesIO()
        Image.new("RGB", (160, 90), (index * 20, 30, 70)).save(out, format="JPEG")
        frames.append((out.getvalue(), 10 + index * 0.2))
    encoded = encode_clip(frames)
    assert encoded[4:8] == b"ftyp"
    with av.open(io.BytesIO(encoded)) as clip:
        decoded = list(clip.decode(video=0))
        assert len(decoded) == 12
        assert decoded[0].width == 160 and decoded[0].height == 90
        assert float(decoded[-1].pts * decoded[-1].time_base) == pytest.approx(
            2.2, abs=0.11
        )
