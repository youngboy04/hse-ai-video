"""Convert the browser demonstration to a portable H.264 MP4."""

from pathlib import Path
from fractions import Fraction
import av

root = Path(__file__).resolve().parents[1] / "docs/demo"
with av.open(str(root / "hse-ai-video.webm")) as source, av.open(
    str(root / "hse-ai-video.mp4"), mode="w", options={"movflags": "+faststart"}
) as target:
    video = source.streams.video[0]
    stream = target.add_stream("libx264", rate=30)
    stream.width = video.width
    stream.height = video.height
    stream.pix_fmt = "yuv420p"
    stream.options = {"preset": "fast", "crf": "23"}
    stream.time_base = Fraction(1, 1000)
    for frame in source.decode(video=0):
        timestamp = frame.time
        frame = frame.reformat(format="yuv420p")
        frame.pts = round(timestamp * 1000)
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            target.mux(packet)
    for packet in stream.encode():
        target.mux(packet)
print(root / "hse-ai-video.mp4")
