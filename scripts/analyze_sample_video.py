"""Analyze licensed sample footage with the installed detector; export an auditable replay."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'public/samples')
    parser.add_argument('--source', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--license', required=True)
    parser.add_argument('--fps', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.fps <= 30:
        parser.error('Analysis FPS must be 1..30')
    model = ROOT/'models/person.onnx'
    if not model.is_file():
        parser.error('Install the real detector first; no simulated results are generated')
    os.environ['DETECTOR_MODEL'] = str(model)
    os.environ['INFERENCE_FPS'] = str(args.fps)
    for env in ('PPE_MODEL','POSE_MODEL','BEHAVIOR_MODEL'):
        os.environ[env] = str(ROOT/'models/not-installed-for-person-video.onnx')
    import av
    import numpy as np
    from PIL import ImageDraw, ImageFont
    from inference.pipeline import Pipeline
    pipeline = Pipeline()
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output/'workers.mp4'
    if args.input.resolve()!=destination.resolve():
        shutil.copyfile(args.input, destination)
    font_path = Path('C:/Windows/Fonts/segoeui.ttf')
    if not font_path.is_file():
        font_path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font=ImageFont.truetype(str(font_path),22)
    small=ImageFont.truetype(str(font_path),17)
    rows=[]
    latest=[]
    last_sample=-10.0
    frame_count=0
    begin=time.perf_counter()
    with av.open(str(args.input)) as source, av.open(str(args.output/'workers-analyzed.mp4'),'w',options={'movflags':'+faststart'}) as output:
        stream=source.streams.video[0]
        fps=stream.average_rate
        encoder=output.add_stream('libx264',rate=fps)
        encoder.width=stream.width; encoder.height=stream.height
        encoder.pix_fmt='yuv420p'
        encoder.options={'crf':'22','preset':'fast'}
        for index, decoded in enumerate(source.decode(stream)):
            image=decoded.to_image().convert('RGB')
            timestamp=float(decoded.time) if decoded.time is not None else index/float(fps)
            if index==0:
                origin=timestamp
            timestamp-=origin
            if timestamp-last_sample >= 1/args.fps-1e-6:
                started=time.perf_counter()
                latest=pipeline.infer(image,'recorded-workers')
                rows.append({'time':round(timestamp,6),'tracks':latest,'latency_ms':round((time.perf_counter()-started)*1000,2)})
                last_sample=timestamp
            draw=ImageDraw.Draw(image)
            for track in latest:
                x1,y1,x2,y2=track['bbox']
                box=(int(x1*image.width),int(y1*image.height),int(x2*image.width),int(y2*image.height))
                draw.rectangle(box,outline='#18e1bb',width=3)
                label=f"ID {track['id']} | {track['confidence']:.0%}"
                tx,ty=box[0]+5,max(42,box[1]+5)
                draw.rectangle((tx-3,ty-2,tx+165,ty+28),fill='#063e37')
                draw.text((tx,ty),label,font=font,fill='white')
            draw.rectangle((0,0,image.width,38),fill='#132338')
            draw.text((14,5),f'HSE | Анализ записи: YOLO11n + ByteTrack | {timestamp:05.2f} с | Людей: {len(latest)}',font=font,fill='white')
            draw.rectangle((0,image.height-32,image.width,image.height),fill='#132338')
            draw.text((14,image.height-28),'Mixkit #1436 | СИЗ и опасные зоны не оцениваются | Не промышленное испытание',font=small,fill='white')
            if index==int(float(fps)*3):
                image.save(args.output/'workers-poster.jpg',quality=92)
            frame=av.VideoFrame.from_image(image)
            for packet in encoder.encode(frame): output.mux(packet)
            frame_count+=1
        for packet in encoder.encode(): output.mux(packet)
        duration=timestamp+1/float(fps)
    report={
        'schema_version':1,'synthetic':False,'mode':'recorded_analysis',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'source':{'title':args.title,'page':args.source,'license':args.license,'credit':'Mixkit, clip 1436','sha256':hashlib.sha256(destination.read_bytes()).hexdigest()},
        'video':{'url':'/samples/workers.mp4','annotated_url':'/samples/workers-analyzed.mp4','width':encoder.width,'height':encoder.height,'duration':round(duration,6),'fps':float(fps),'decoded_frames':frame_count},
        'analysis':{'sample_fps':args.fps,'samples':len(rows),'model':pipeline.model_info['detector'],'provider':pipeline.provider,'track_ids':sorted({t['id'] for row in rows for t in row['tracks']}),'frames_with_people':sum(bool(row['tracks']) for row in rows),'median_ms':round(float(np.median([r['latency_ms'] for r in rows])),2),'total_processing_seconds':round(time.perf_counter()-begin,2)},
        'limitations':['Показывается сохранённый результат реального инференса; воспроизведение не запускает модель заново.','Идентификатор относится к треку внутри записи, а не к личности сотрудника.','Каски и жилеты видны на исходном видео, но не распознаются подключённой моделью.','Крупный план не позволяет достоверно проверить положение ног в опасной зоне.','Ролик не является пилотом на предприятии; эталонная разметка и оценка точности отсутствуют.'],
        'frames':rows,
    }
    (args.output/'workers-analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:report[k] for k in ('video','analysis')},ensure_ascii=True))


if __name__=='__main__':main()
