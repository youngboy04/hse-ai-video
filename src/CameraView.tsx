import { useEffect, useRef, useState } from "react";
import { Maximize2, Pause, Play, VideoOff, ScanLine } from "lucide-react";
import type { Camera, Frame, Track, Zone } from "./types";
import { useUI } from "./store";
import { warehouse, person } from "./scene";

interface Props {
  camera: Camera;
  zones?: Zone[];
  overlays?: boolean;
  large?: boolean;
  onExpand?: () => void;
  onPoint?: (point: [number, number]) => void;
  draft?: [number, number][];
}
export default function CameraView({
  camera,
  zones = [],
  overlays = true,
  large = false,
  onExpand,
  onPoint,
  draft = [],
}: Props) {
  const canvas = useRef<HTMLCanvasElement>(null),
    frame = useRef<Frame | null>(null),
    bitmap = useRef<ImageBitmap | null>(null),
    positions = useRef(new Map<number, number[]>());
  const [paused, setPaused] = useState(false),
    [connected, setConnected] = useState(false),
    [time, setTime] = useState("");
  const token = useUI((s) => s.token);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;
  const renderState = useRef({ zones, overlays, draft, camera });
  renderState.current = { zones, overlays, draft, camera };
  useEffect(() => {
    let disposed = false,
      retry: ReturnType<typeof setTimeout>,
      watchdog: ReturnType<typeof setInterval>,
      socket: WebSocket,
      last = 0;
    const connect = () => {
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws/${camera.id}`,
      );
      socket.binaryType = "arraybuffer";
      socket.onopen = () => socket.send(JSON.stringify({ token }));
      socket.onmessage = async (event) => {
        if (disposed) return;
        if (typeof event.data === "string") {
          const data = JSON.parse(event.data);
          if (data.type === "frame") {
            last = Date.now();
            setConnected(true);
            if (!pausedRef.current) {
              frame.current = data;
              setTime(new Date(data.timestamp).toLocaleTimeString("ru-RU"));
            }
          }
        } else if (!pausedRef.current) {
          try {
            const next = await createImageBitmap(
              new Blob([event.data], { type: "image/jpeg" }),
            );
            if (disposed || pausedRef.current) {
              next.close();
              return;
            }
            bitmap.current?.close();
            bitmap.current = next;
          } catch {
            /* Invalid frame leaves the last valid image. */
          }
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (!disposed) retry = setTimeout(connect, 2500);
      };
      socket.onerror = () => socket.close();
    };
    if (camera.enabled) connect();
    watchdog = setInterval(() => {
      if (Date.now() - last > 8000) setConnected(false);
    }, 1000);
    return () => {
      disposed = true;
      clearTimeout(retry);
      clearInterval(watchdog);
      socket?.close();
      bitmap.current?.close();
      bitmap.current = null;
      frame.current = null;
      positions.current.clear();
    };
  }, [camera.id, camera.enabled, token]);
  useEffect(() => {
    let raf = 0;
    const draw = (now: number) => {
      const el = canvas.current;
      if (!el) return;
      const ctx = el.getContext("2d");
      if (!ctx) return;
      const width = Math.max(1, Math.round(el.clientWidth * devicePixelRatio)),
        height = Math.max(1, Math.round(el.clientHeight * devicePixelRatio));
      if (el.width !== width || el.height !== height) {
        el.width = width;
        el.height = height;
      }
      const state = renderState.current;
      if (!pausedRef.current || onPoint) {
        if (state.camera.demo)
          warehouse(
            ctx,
            width,
            height,
            parseInt(state.camera.id.slice(-1), 16) || 1,
            now / 1000,
          );
        else if (bitmap.current)
          ctx.drawImage(bitmap.current, 0, 0, width, height);
        else {
          ctx.fillStyle = "#182733";
          ctx.fillRect(0, 0, width, height);
        }
        if (state.overlays) {
          for (const zone of state.zones.filter(
            (z) => z.camera_id === state.camera.id && z.enabled,
          ))
            drawZone(ctx, zone.points, width, height, zone.name, false);
          if (state.draft.length)
            drawZone(ctx, state.draft, width, height, "Новая зона", true);
        }
        const active = new Set((frame.current?.tracks || []).map((t) => t.id));
        for (const id of positions.current.keys())
          if (!active.has(id)) positions.current.delete(id);
        for (const track of frame.current?.tracks || []) {
          const previous = positions.current.get(track.id) || [...track.bbox];
          const box = previous.map((v, i) => v + (track.bbox[i] - v) * 0.12);
          positions.current.set(track.id, box);
          if (state.camera.demo)
            person(
              ctx,
              box[0] * width,
              box[1] * height,
              (box[2] - box[0]) * width,
              (box[3] - box[1]) * height,
              track.helmet,
              track.vest,
            );
          if (state.overlays)
            drawTrack(
              ctx,
              { ...track, bbox: box as Track["bbox"] },
              width,
              height,
            );
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [onPoint]);
  return (
    <div
      className={`camera-view ${large ? "large" : ""} ${onPoint ? "drawing" : ""}`}
    >
      <canvas
        ref={canvas}
        aria-label={`Видеопоток: ${camera.name}`}
        onClick={(e) => {
          if (onPoint) {
            const r = e.currentTarget.getBoundingClientRect();
            onPoint([
              (e.clientX - r.left) / r.width,
              (e.clientY - r.top) / r.height,
            ]);
          }
        }}
      />
      <div className="camera-top">
        <span className="feed-label">
          <span className={`dot ${connected ? "green" : "gray"}`} />
          {camera.id.replace("cam-", "CAM ").toUpperCase()}
        </span>
        <span className="camera-clock">{time || "—:—:—"}</span>
      </div>
      {(!connected || !camera.enabled) && !onPoint && (
        <div className="feed-offline">
          <VideoOff size={25} />
          <span>
            {camera.enabled ? "Ожидание потока" : "Камера приостановлена"}
          </span>
        </div>
      )}
      <div className="camera-bottom">
        <span>
          {camera.demo
            ? "СИНТЕТИЧЕСКОЕ ДЕМО"
            : connected
              ? "ПРЯМОЙ ЭФИР"
              : "НЕТ СИГНАЛА"}
        </span>
        <div>
          {overlays && (
            <span className="ai-tag">
              <ScanLine size={11} /> Треки
            </span>
          )}
          <button
            title={paused ? "Продолжить" : "Пауза"}
            onClick={() => setPaused(!paused)}
          >
            {paused ? <Play size={14} /> : <Pause size={14} />}
          </button>
          {onExpand && (
            <button title="Развернуть камеру" onClick={onExpand}>
              <Maximize2 size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
function drawZone(
  ctx: CanvasRenderingContext2D,
  points: [number, number][],
  w: number,
  h: number,
  label: string,
  draft: boolean,
) {
  if (!points.length) return;
  ctx.save();
  ctx.beginPath();
  points.forEach(([x, y], i) =>
    i ? ctx.lineTo(x * w, y * h) : ctx.moveTo(x * w, y * h),
  );
  if (points.length > 2) ctx.closePath();
  ctx.fillStyle = draft ? "rgba(33,201,172,.17)" : "rgba(248,177,70,.12)";
  ctx.fill();
  ctx.strokeStyle = draft ? "#25dab4" : "#edb14c";
  ctx.lineWidth = 1.5 * devicePixelRatio;
  ctx.setLineDash([5 * devicePixelRatio, 4 * devicePixelRatio]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.font = `${10 * devicePixelRatio}px sans-serif`;
  ctx.fillStyle = draft ? "#3cf7ca" : "#ffcf78";
  ctx.fillText(label, points[0][0] * w + 5, points[0][1] * h - 7);
  if (draft)
    for (const [x, y] of points) {
      ctx.beginPath();
      ctx.arc(x * w, y * h, 4 * devicePixelRatio, 0, Math.PI * 2);
      ctx.fill();
    }
  ctx.restore();
}
function drawTrack(
  ctx: CanvasRenderingContext2D,
  track: Track,
  w: number,
  h: number,
) {
  const [x1, y1, x2, y2] = track.bbox,
    unsafe = track.helmet === false || track.vest === false || track.fall;
  const color = unsafe ? "#fb6868" : "#37dfac";
  const scale = devicePixelRatio;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.3 * scale;
  ctx.strokeRect(
    x1 * w - 4 * scale,
    y1 * h - 3 * scale,
    (x2 - x1) * w + 8 * scale,
    (y2 - y1) * h + 6 * scale,
  );
  const label = `#${track.id} ${track.helmet === false ? "БЕЗ КАСКИ" : track.vest === false ? "БЕЗ ЖИЛЕТА" : track.helmet === null ? "СИЗ ?" : "СИЗ ✓"}`;
  ctx.font = `${9 * scale}px sans-serif`;
  const textw = ctx.measureText(label).width;
  ctx.fillStyle = color;
  ctx.fillRect(
    x1 * w - 4 * scale,
    y1 * h - 17 * scale,
    textw + 8 * scale,
    14 * scale,
  );
  ctx.fillStyle = "#123b39";
  ctx.fillText(label, x1 * w, y1 * h - 7 * scale);
  if (track.pose) {
    const edges = [
      [5, 6],
      [5, 7],
      [7, 9],
      [6, 8],
      [8, 10],
      [5, 11],
      [6, 12],
      [11, 12],
      [11, 13],
      [13, 15],
      [12, 14],
      [14, 16],
    ];
    for (const [a, b] of edges) {
      const p = track.pose[a],
        q = track.pose[b];
      if (p && q && p[2] > 0.4 && q[2] > 0.4) {
        ctx.beginPath();
        ctx.moveTo(p[0] * w, p[1] * h);
        ctx.lineTo(q[0] * w, q[1] * h);
        ctx.stroke();
      }
    }
  }
  ctx.restore();
}
