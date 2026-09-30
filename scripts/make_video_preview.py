"""Build the README animation from the measured, annotated video."""
from pathlib import Path
import av
from PIL import Image

root=Path(__file__).resolve().parents[1]
frames=[]
last=-1.0
with av.open(str(root/'public/samples/workers-analyzed.mp4')) as source:
    for frame in source.decode(video=0):
        timestamp=float(frame.time)
        if timestamp-last < 1/3-1e-6:
            continue
        last=timestamp
        image=frame.to_image()
        image.thumbnail((640,360),Image.Resampling.LANCZOS)
        frames.append(image.quantize(colors=96,dither=Image.Dither.NONE))
target=root/'docs/demo/workers-preview.gif'
frames[0].save(target,save_all=True,append_images=frames[1:],duration=333,loop=0,optimize=True,disposal=2)
print(f'{len(frames)} preview frames, {target.stat().st_size} bytes')
