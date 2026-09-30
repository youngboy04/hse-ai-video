"""Explicit person-detection metrics at a fixed score and IoU threshold."""
import math


def overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = max(0, a[2]-a[0])*max(0, a[3]-a[1]) + max(0, b[2]-b[0])*max(0, b[3]-b[1]) - intersection
    return intersection / union if union else 0.0


def match_detections(predictions, targets, iou_threshold=0.5):
    """Score-ordered one-to-one matching, including negative images and duplicates."""
    if not 0 < iou_threshold <= 1:
        raise ValueError("IoU threshold must be in (0,1]")
    matched = set()
    tp = 0
    for prediction in sorted(predictions, key=lambda item: item['confidence'], reverse=True):
        candidates = [(overlap(prediction['bbox'], box), index) for index, box in enumerate(targets) if index not in matched]
        best = max(candidates, default=(0, -1))
        if best[0] >= iou_threshold:
            matched.add(best[1])
            tp += 1
    return {'tp': tp, 'fp': len(predictions)-tp, 'fn': len(targets)-tp}


def summarize(counts):
    totals = {key: sum(row[key] for row in counts) for key in ('tp','fp','fn')}
    tp, fp, fn = (totals[k] for k in ('tp','fp','fn'))
    return {**totals, 'precision': tp/(tp+fp) if tp+fp else None,
            'recall': tp/(tp+fn) if tp+fn else None,
            'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def read_yolo_people(path, class_id=0):
    """Require an explicit label file, including an empty file for negatives."""
    if not path.is_file():
        raise ValueError(f'Missing labels for {path.name}; negatives require an empty file')
    boxes=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        parts=line.split()
        if len(parts)!=5:
            raise ValueError(f'Expected 5 YOLO detection fields in {path.name}')
        category, x, y, w, h=map(float,parts)
        if not all(math.isfinite(v) for v in (category,x,y,w,h)) or category<0 or not category.is_integer() or not all(0<=v<=1 for v in (x,y,w,h)) or w<=0 or h<=0:
            raise ValueError(f'Invalid YOLO annotation in {path.name}')
        if category==class_id:
            boxes.append([max(0,x-w/2),max(0,y-h/2),min(1,x+w/2),min(1,y+h/2)])
    return boxes
