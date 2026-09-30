from pathlib import Path
import io
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from inference.evaluation import match_detections, summarize, read_yolo_people


def test_matching_counts_duplicates_negatives_and_misses():
    target=[0,0,.4,.4]
    predictions=[{'bbox':target,'confidence':.9},{'bbox':target,'confidence':.7}]
    assert match_detections(predictions,[target,[.6,.6,1,1]])=={'tp':1,'fp':1,'fn':1}
    assert match_detections(predictions,[])=={'tp':0,'fp':2,'fn':0}
    assert match_detections([], [target])=={'tp':0,'fp':0,'fn':1}
    assert summarize([])['precision'] is None
    assert summarize([{'tp':1,'fp':1,'fn':3}])['recall']==.25


def test_matching_uses_score_order_and_iou_threshold():
    rows=[{'bbox':[.1,0,.5,.4],'confidence':.9},{'bbox':[0,0,.4,.4],'confidence':.8}]
    assert match_detections(rows,[[0,0,.4,.4]],.9)=={'tp':1,'fp':1,'fn':0}
    with pytest.raises(ValueError): match_detections([],[],0)


def test_missing_label_is_not_silently_counted_as_negative(tmp_path):
    path=tmp_path/'frame.txt'
    with pytest.raises(ValueError,match='Missing labels'): read_yolo_people(path)
    path.write_text('')
    assert read_yolo_people(path)==[]
    path.write_text('0 .5 .5 .2 .4\n1 .5 .5 .4 .4')
    assert read_yolo_people(path)[0]==pytest.approx([.4,.3,.6,.7])
    path.write_text('0 nan .5 .2 .2')
    with pytest.raises(ValueError): read_yolo_people(path)


@pytest.fixture
def analysis_client(monkeypatch):
    import inference.main as main
    pipeline=SimpleNamespace(models={'detector':True},provider='CPUExecutionProvider',model_info={'detector':{'file':'fixture.onnx','sha256':'fixture'}},
        detect=lambda image:(np.array([[0,0,image.width,image.height],[1,1,3,3]]),np.array([.9,.2])))
    monkeypatch.setenv('SERVICE_TOKEN','analysis-service')
    monkeypatch.setattr(main,'Pipeline',lambda:pipeline)
    with TestClient(main.app) as client: yield client


def test_image_analysis_is_stateless_filtered_and_authenticated(analysis_client):
    buf=io.BytesIO(); Image.new('RGB',(50,30)).save(buf,format='PNG')
    files={'frame':('image.png',buf.getvalue(),'image/png')}
    assert analysis_client.post('/analyze',files=files).status_code==401
    response=analysis_client.post('/analyze',files=files,headers={'X-Service-Token':'analysis-service'})
    assert response.status_code==200
    result=response.json()
    assert len(result['detections'])==1
    assert result['detections'][0]['bbox']==[0,0,1,1]
    assert len(result['image_sha256'])==64
    assert result['scope']=='person_detection' and not result['synthetic']
    assert 'tracks' not in result


def test_image_analysis_rejects_bad_files_limits_and_threshold(analysis_client):
    headers={'X-Service-Token':'analysis-service'}
    assert analysis_client.post('/analyze',headers=headers,files={'frame':('bad.png',b'bad')}).status_code==422
    assert analysis_client.post('/analyze',headers=headers,files={'frame':('big.png',b'x'*(3*1024*1024+1))}).status_code==413
    assert analysis_client.post('/analyze',headers=headers,data={'confidence':'1.1'},files={'frame':('bad.png',b'bad')}).status_code==422


def test_image_analysis_respects_exif_orientation(analysis_client):
    buf=io.BytesIO(); image=Image.new('RGB',(50,30)); exif=Image.Exif();exif[274]=6;image.save(buf,format='JPEG',exif=exif)
    result=analysis_client.post('/analyze',headers={'X-Service-Token':'analysis-service'},files={'frame':('rotated.jpg',buf.getvalue())}).json()
    assert (result['width'],result['height'])==(30,50)
