import { useEffect, useRef, useState } from "react";
import { Download, ScanLine } from "lucide-react";
import "./video-sample.css";

type Track = { id: number; bbox: [number,number,number,number]; confidence: number; helmet: null; vest: null };
type Frame = { time: number; tracks: Track[]; latency_ms: number };
type Replay = {
  mode: "recorded_analysis"; synthetic: false;
  source: { title: string; page: string; license: string; credit: string; sha256: string };
  video: { url: string; annotated_url: string; width: number; height: number; duration: number };
  analysis: { samples: number; sample_fps: number; model: { file: string; sha256: string }; provider: string; track_ids: number[]; median_ms: number };
  frames: Frame[]; limitations: string[];
};

function frameAt(frames: Frame[], time: number): Frame | null {
  let low=0, high=frames.length-1, found=-1;
  while(low<=high){ const mid=(low+high)>>1; if(frames[mid].time<=time){found=mid;low=mid+1;}else high=mid-1; }
  if(found<0 || time-frames[found].time>.3)return null;
  return frames[found];
}

export default function VideoSamplePage(){
  const [data,setData]=useState<Replay|null>(null);
  const [error,setError]=useState("");
  const [overlay,setOverlay]=useState(true);
  const [current,setCurrent]=useState<Frame|null>(null);
  const video=useRef<HTMLVideoElement>(null);
  const canvas=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{
    const controller=new AbortController();
    fetch('/samples/workers-analysis.json',{signal:controller.signal}).then(async r=>{
      if(!r.ok)throw Error('Файлы анализа не найдены. Подготовьте тестовый ролик по инструкции.');
      const body=await r.json();
      if(body.synthetic!==false || body.mode!=='recorded_analysis' || !body.frames?.length)throw Error('Неверный протокол видео');
      setData(body);
    }).catch(e=>{if(e.name!=='AbortError')setError(e.message)});
    return()=>controller.abort();
  },[]);
  useEffect(()=>{
    if(!data)return;
    let raf=0, lastTime=-1, lastRow:Frame|null|undefined;
    const draw=()=>{
      const player=video.current, surface=canvas.current;
      if(player && surface && player.currentTime!==lastTime){
        lastTime=player.currentTime;
        const row=frameAt(data.frames,lastTime);
        if(row!==lastRow){setCurrent(row);lastRow=row;}
        const ctx=surface.getContext('2d');
        if(ctx){
          ctx.clearRect(0,0,surface.width,surface.height);
          if(overlay && row){
            ctx.font='22px Segoe UI, sans-serif';ctx.lineWidth=3;
            for(const track of row.tracks){
              const [x1,y1,x2,y2]=track.bbox;
              const x=x1*surface.width,y=y1*surface.height;
              ctx.strokeStyle='#18e1bb';ctx.strokeRect(x,y,(x2-x1)*surface.width,(y2-y1)*surface.height);
              const label=`ID ${track.id} · ${Math.round(track.confidence*100)}%`,ty=Math.max(30,y+30);
              ctx.fillStyle='#063e37';ctx.fillRect(x+3,ty-25,ctx.measureText(label).width+16,32);
              ctx.fillStyle='#fff';ctx.fillText(label,x+10,ty);
            }
          }
        }
      }
      raf=requestAnimationFrame(draw);
    };
    draw();return()=>cancelAnimationFrame(raf);
  },[data,overlay]);
  if(error)return <div className="error-banner" role="alert">{error}</div>;
  if(!data)return <p className="muted">Загрузка тестового видео…</p>;
  return <div className="sample-page">
    <div className="sample-intro"><div><h2>Рабочие на строительном участке</h2><p>Реальная съёмка · {data.video.duration.toFixed(1)} с · сохранённый анализ YOLO11n + ByteTrack</p></div>
      <button className="button" aria-pressed={overlay} onClick={()=>setOverlay(!overlay)}><ScanLine size={16}/>Разметка видео</button>
    </div>
    <div className="sample-layout">
      <section className="sample-player-panel">
        <div className="sample-player">
          <video ref={video} src={data.video.url} controls playsInline preload="auto" aria-label="Видео с рабочими" onError={()=>setError('Не удалось открыть видео. Проверьте наличие файла samples/workers.mp4.')}/>
          <canvas ref={canvas} width={data.video.width} height={data.video.height} aria-label="Рамки и идентификаторы треков" hidden={!overlay}/>
        </div>
        <p className="sample-note">Воспроизводится запись с результатами настоящего инференса, рассчитанными заранее. Перемотка синхронизирует рамки с кадром.</p>
        <div className="sample-downloads"><a className="button" href={data.video.annotated_url} download="HSE-workers-analysis.mp4"><Download size={16}/>Скачать видео с разметкой</a><a className="button" href="/samples/workers-analysis.json" download><Download size={16}/>Протокол JSON</a></div>
      </section>
      <section className="sample-tracks">
        <h2>Результат на кадре</h2>
        <div className="sample-count"><strong>{current?.tracks.length ?? 0}</strong><span>обнаружено людей</span></div>
        <p className="muted">Метка анализа: {current?.time.toFixed(2) ?? '0.00'} с</p>
        <div className="sample-track-list">{current?.tracks.map(track=><div className="sample-track" key={track.id}><strong>Трек #{track.id}</strong><span>Уверенность: {Math.round(track.confidence*100)}%</span><small>Каска / жилет: не оцениваются</small></div>)}</div>
        {!current?.tracks.length && <p className="muted">На этом кадре подтверждённых треков нет.</p>}
        <p className="sample-note">ID связывает наблюдения внутри ролика. Он не определяет личность человека. Уверенность модели не равна точности.</p>
      </section>
    </div>
    <section className="sample-explanation"><h2>Как проходит анализ</h2><ol><li>Из записи выбирается до {data.analysis.sample_fps} кадров в секунду.</li><li>YOLO11n находит людей и возвращает координаты рамок.</li><li>ByteTrack сопоставляет наблюдения и назначает ID треков.</li><li>Браузер совмещает сохранённые координаты со временем видео.</li></ol>
      <p>Каски и жилеты видны на видео, но соответствующая модель ещё не подключена. Контроль опасной зоны требует ракурса с видимыми ногами; в этой записи он не выполняется. События ролика не попадают в журнал рабочих камер.</p>
      <details><summary>Протокол и происхождение видео</summary><p>{data.analysis.samples} обработанных кадров; медиана инференса {data.analysis.median_ms.toFixed(1)} мс, {data.analysis.provider}. Это не измерение точности или производительности видеосервера.</p><p>Модель: {data.analysis.model.file}</p><code>{data.analysis.model.sha256}</code><p>Видео: <a href={data.source.page} target="_blank" rel="noreferrer">{data.source.title}, {data.source.credit}</a>. <a href={data.source.license} target="_blank" rel="noreferrer">Лицензия</a>.</p><code>{data.source.sha256}</code>{data.limitations.map(s=><p key={s}>{s}</p>)}</details>
    </section>
  </div>;
}
