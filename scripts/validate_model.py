"""Reproducible dataset check of the actual exported detector, never synthetic boxes."""
import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import sys
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',type=Path,required=True,help='Root with images/<split> and labels/<split>')
    parser.add_argument('--splits',nargs='+',default=['val'])
    parser.add_argument('--name',required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--purpose',choices=['smoke_test','independent_test'],default='smoke_test')
    parser.add_argument('--limitations',required=True,help='Provenance, overlap with training and site restrictions')
    parser.add_argument('--model',type=Path,default=ROOT/'models/person.onnx')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/evidence')
    parser.add_argument('--confidence',type=float,default=.35)
    parser.add_argument('--iou',type=float,default=.5)
    args=parser.parse_args()
    if not .1<=args.confidence<=1 or not 0<args.iou<=1:
        parser.error('Confidence must be in [0.1,1], IoU in (0,1]')
    if not args.model.is_file():
        parser.error('Detector model is missing. Run scripts/export_models.py first.')
    import numpy as np
    import onnxruntime as ort
    from PIL import Image
    from inference.pipeline import Pipeline
    from inference.evaluation import read_yolo_people,match_detections,summarize
    os.environ['DETECTOR_MODEL']=str(args.model.resolve())
    # This evaluation measures only person detection, irrespective of optional heads.
    for env in ['PPE_MODEL','POSE_MODEL','BEHAVIOR_MODEL']:
        os.environ[env]=str(args.output/'not-loaded-for-detection-evaluation.onnx')
    pipeline=Pipeline()
    files=[]
    for split in args.splits:
        if split not in ('train','val','test'):
            parser.error('Splits must be train, val or test')
        files.extend(sorted(p for p in (args.dataset/'images'/split).glob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}))
    if not files or len(set(files))!=len(files):
        parser.error('Dataset is empty or splits are duplicated')
    manifest=[]
    for path in files:
        label=args.dataset/'labels'/path.parent.name/(path.stem+'.txt')
        targets=read_yolo_people(label)
        manifest.append((path,label,targets))
    warmup=Image.open(files[0]).convert('RGB')
    for _ in range(3): pipeline.detect(warmup)
    results=[]
    dataset_hash=hashlib.sha256()
    gallery=[]
    for path,label,targets in manifest:
        image=Image.open(path).convert('RGB')
        started=time.perf_counter()
        boxes,scores=pipeline.detect(image)
        elapsed=(time.perf_counter()-started)*1000
        predictions=[{'bbox':[float(b[0])/image.width,float(b[1])/image.height,float(b[2])/image.width,float(b[3])/image.height], 'confidence':float(s)} for b,s in zip(boxes,scores) if s>=args.confidence]
        relative=path.relative_to(args.dataset).as_posix()
        image_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        label_hash=hashlib.sha256(label.read_bytes()).hexdigest()
        dataset_hash.update(f'{relative}\0{image_hash}\0{label_hash}\n'.encode())
        row={'image':relative,'image_sha256':image_hash,'label_sha256':label_hash,'targets':targets,'predictions':predictions,'latency_ms':round(elapsed,3),**match_detections(predictions,targets,args.iou)}
        results.append(row)
        # Native SVG overlay: coordinates are the measured detections and reference labels.
        rectangles=''.join(f'<rect x="{b[0]*100}" y="{b[1]*100}" width="{(b[2]-b[0])*100}" height="{(b[3]-b[1])*100}" fill="none" stroke="{color}" stroke-width=".4"/>' for group,color in [(targets,'#29a5ff'),([p['bbox'] for p in predictions],'#30d59c')] for b in group)
        mime='image/png' if path.suffix.lower()=='.png' else 'image/webp' if path.suffix.lower()=='.webp' else 'image/jpeg'
        gallery.append(f'<figure><div class="image"><img src="data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}" alt="{html.escape(relative)}"><svg viewBox="0 0 100 100" preserveAspectRatio="none">{rectangles}</svg></div><figcaption>{html.escape(relative)}: TP {row["tp"]}, FP {row["fp"]}, FN {row["fn"]}</figcaption></figure>')
    latency=[r['latency_ms'] for r in results]
    report={'schema_version':1,'created_at':datetime.now(timezone.utc).isoformat(),'scope':'person_detection','purpose':args.purpose,
            'dataset':{'name':args.name,'source':args.source,'splits':args.splits,'sha256':dataset_hash.hexdigest(),'images':len(results),'people':sum(len(r['targets']) for r in results),'negative_images':sum(not r['targets'] for r in results)},
            'model':pipeline.model_info['detector'],'runtime':{'provider':pipeline.provider,'python':platform.python_version(),'onnxruntime':ort.__version__,'platform':platform.platform(),'processor':platform.processor()},
            'thresholds':{'confidence':args.confidence,'iou':args.iou},'metrics':summarize(results),
            'latency':{'median_ms':round(float(np.median(latency)),2),'p95_ms':round(float(np.percentile(latency,95)),2),'warmup_frames':3,'samples':len(latency),'scope':'preprocess + ONNX + postprocess, excludes disk I/O'},
            'limitations':[args.limitations,'Проверяется только обнаружение людей. Качество СИЗ, падений, трекинга и инцидентов этим набором не оценивается.','Это измерение на данном наборе и компьютере. Оно не подтверждает работу на производстве или производительность нескольких камер.'],
            'results':results}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    m=report['metrics']; pct=lambda n:'н/д' if n is None else f'{n*100:.1f}%'
    intro=f'<h1>Протокол проверки детектора</h1><p>{html.escape(args.name)}. {len(results)} изображений, {report["dataset"]["people"]} людей в разметке.</p><p>Precision {pct(m["precision"])} · Recall {pct(m["recall"])} · TP {m["tp"]} · FP {m["fp"]} · FN {m["fn"]}</p><p>Порог confidence {args.confidence}, IoU {args.iou}. Медиана {report["latency"]["median_ms"]} мс, p95 {report["latency"]["p95_ms"]} мс.</p>'
    caveats='<ul>'+''.join('<li>'+html.escape(t)+'</li>' for t in report['limitations'])+'</ul>'
    details=f'<p>Модель SHA-256: <code>{report["model"]["sha256"]}</code></p><p>Набор SHA-256: <code>{report["dataset"]["sha256"]}</code></p><p>Источник: {html.escape(args.source)}</p><p>Дата UTC: {report["created_at"]}. {html.escape(pipeline.provider)}. Python {platform.python_version()}, ONNX Runtime {ort.__version__}.</p>'
    (args.output/'report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>HSE: протокол проверки</title><style>body{font:16px Arial;max-width:1160px;margin:40px auto;padding:0 24px;color:#1e293b}p,li{line-height:1.6}code{overflow-wrap:anywhere}.gallery{display:grid;grid-template-columns:1fr 1fr;gap:24px}figure{margin:0}.image{position:relative}img{display:block;width:100%}svg{position:absolute;inset:0;width:100%;height:100%}figcaption{padding:10px 0}@media(max-width:700px){.gallery{grid-template-columns:1fr}}</style>'+intro+caveats+details+'<p>Синие рамки: эталон. Зелёные рамки: предсказания модели.</p><div class="gallery">'+''.join(gallery)+'</div></html>',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['dataset','metrics','latency']},ensure_ascii=True))


if __name__=='__main__': main()
