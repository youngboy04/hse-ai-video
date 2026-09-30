import { useEffect, useState } from "react";
import { Download, LoaderCircle, Upload, RefreshCw } from "lucide-react";
import { api } from "./api";
import { useUI } from "./store";
import "./validation.css";

type Detection = { bbox: [number, number, number, number]; confidence: number };
type Analysis = {
  width: number; height: number; latency_ms: number; provider: string;
  model: { file: string; sha256: string }; image_sha256: string;
  detections: Detection[]; limitations: string[];
};
type Report = {
  created_at: string; purpose: string;
  dataset: { name: string; images: number; people: number; negative_images: number; source: string; sha256: string };
  model: { file: string; sha256: string };
  metrics: { tp: number; fp: number; fn: number; precision: number | null; recall: number | null };
  latency: { median_ms: number; p95_ms: number };
  thresholds: { confidence: number; iou: number }; limitations: string[];
};
const percentage = (n: number | null) => n === null ? "Нет данных" : `${(n * 100).toFixed(1)}%`;
function download(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ValidationPage() {
  const token = useUI(s => s.token);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [threshold, setThreshold] = useState(.35);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [reportError, setReportError] = useState("");
  const refresh = () => api<Report>("/validation/report").then(r => { setReport(r); setReportError(""); }).catch(e => setReportError(e.message));
  useEffect(() => { void refresh(); }, [token]);
  useEffect(() => {
    if (!file) { setPreview(""); return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  async function run() {
    if (!file || busy) return;
    setBusy(true); setError(""); setAnalysis(null);
    const data = new FormData(); data.append("frame", file); data.append("confidence", String(threshold));
    try {
      const response = await fetch("/api/validation/image", { method: "POST", body: data, headers: token ? { Authorization: `Bearer ${token}` } : {} });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Не удалось обработать изображение");
      setAnalysis(body);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="validation-page">
    <section className="validation-panel">
      <h2>Проверка на изображении</h2>
      <p className="muted">Загрузите JPEG, PNG или WebP до 3 МиБ. Изображение обрабатывается локальным сервисом и не добавляется в журнал инцидентов.</p>
      <div className="validation-controls">
        <label className="button"><Upload size={16} /> Выбрать изображение
          <input aria-label="Изображение для проверки" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={e => {
            const next = e.target.files?.[0] ?? null; setAnalysis(null); setError("");
            if (next && next.size > 3 * 1024 * 1024) { setError("Изображение должно быть не больше 3 МиБ"); setFile(null); return; }
            setFile(next);
          }} />
        </label>
        <label className="validation-threshold">Порог уверенности
          <select aria-label="Порог уверенности" value={threshold} disabled={busy} onChange={e => { setThreshold(Number(e.target.value)); setAnalysis(null); }}>
            {[.1,.2,.35,.5,.65,.8,.9].map(n => <option key={n} value={n}>{n.toFixed(2)}</option>)}
          </select>
        </label>
        <button className="button primary" disabled={!file || busy} onClick={() => void run()}>{busy ? <LoaderCircle size={16} className="spin" /> : null}{busy ? "Обработка…" : "Проверить"}</button>
        {analysis && <button className="button" onClick={() => download(analysis, "hse-image-result.json")}><Download size={16} /> Результат JSON</button>}
      </div>
      {error && <div className="validation-error" role="alert">{error}</div>}
      {preview ? <div className="validation-image">
        <img src={preview} alt={file?.name ?? "Изображение для проверки"} />
        {analysis && <svg viewBox={`0 0 ${analysis.width} ${analysis.height}`} role="img" aria-label={`Обнаружено людей: ${analysis.detections.length}`}>
          {analysis.detections.map((d, i) => <g key={i}>
            <rect x={d.bbox[0]*analysis.width} y={d.bbox[1]*analysis.height} width={(d.bbox[2]-d.bbox[0])*analysis.width} height={(d.bbox[3]-d.bbox[1])*analysis.height} fill="none" stroke="#10b981" strokeWidth={Math.max(2,analysis.width/350)} />
            <text x={d.bbox[0]*analysis.width+4} y={d.bbox[1]*analysis.height+Math.max(18,analysis.width/40)} fill="#ffffff" stroke="#064e3b" strokeWidth=".5" fontSize={Math.max(16,analysis.width/45)}>{i+1}: {Math.round(d.confidence*100)}%</text>
          </g>)}
        </svg>}
      </div> : <div className="validation-empty">Выберите кадр с людьми для проверки детектора</div>}
      {analysis && <div className="validation-result" aria-live="polite">
        <h3>Обнаружено людей: {analysis.detections.length}</h3>
        <p>Обработка кадра: {analysis.latency_ms.toFixed(1)} мс. {analysis.provider}.</p>
        <p>СИЗ и падения в этой проверке не оцениваются. Рамки показывают обнаружения одного кадра, без трекинга.</p>
        <details><summary>Модель и ограничения</summary><p>{analysis.model.file}</p><code>{analysis.model.sha256}</code>{analysis.limitations.map(s => <p key={s}>{s}</p>)}</details>
      </div>}
    </section>
    <section className="validation-panel">
      <div className="validation-report-heading"><h2>Протокол проверки набора данных</h2><button className="button" onClick={() => void refresh()}><RefreshCw size={15} /> Обновить</button></div>
      {!report ? <p className="muted">{reportError || "Загрузка протокола…"}</p> : <>
        <p><strong>{report.dataset.name}</strong> — {report.dataset.images} изображений, {report.dataset.people} людей в эталонной разметке, {report.dataset.negative_images} кадров без людей.</p>
        <p className="validation-scope">{report.purpose === "smoke_test" ? "Функциональная проверка на небольшом наборе. Не является независимым испытанием точности." : "Результаты относятся только к указанному набору данных."}</p>
        <div className="validation-metrics">
          <div><span>Precision</span><strong>{percentage(report.metrics.precision)}</strong></div>
          <div><span>Recall</span><strong>{percentage(report.metrics.recall)}</strong></div>
          <div><span>Ложные обнаружения</span><strong>{report.metrics.fp}</strong></div>
          <div><span>Пропущенные люди</span><strong>{report.metrics.fn}</strong></div>
          <div><span>Обработка p95</span><strong>{report.latency.p95_ms.toFixed(1)} мс</strong></div>
        </div>
        <p>Порог уверенности: {report.thresholds.confidence}. IoU для сопоставления: {report.thresholds.iou}. Совпавших обнаружений: {report.metrics.tp}.</p>
        <details><summary>Условия испытаний</summary><p>{new Date(report.created_at).toLocaleString("ru-RU")}</p><p>Модель: {report.model.file}</p><code>{report.model.sha256}</code>{report.limitations.map(s => <p key={s}>{s}</p>)}<p>Источник: {report.dataset.source}</p></details>
        <button className="button" onClick={() => download(report, "hse-validation-report.json")}><Download size={16} /> Скачать протокол JSON</button>
      </>}
    </section>
  </div>;
}
