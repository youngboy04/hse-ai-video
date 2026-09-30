export type Page =
  "overview" | "cameras" | "incidents" | "zones" | "analytics" | "validation" | "sample" | "settings";
export type IncidentKind = "no_helmet" | "no_vest" | "zone" | "fall";
export interface Camera {
  id: string;
  name: string;
  location: string;
  source: string;
  enabled: boolean;
  online: boolean;
  fps: number;
  latency_ms: number;
  demo: boolean;
}
export interface Incident {
  id: string;
  camera_id: string;
  camera_name: string;
  track_id: number;
  kind: IncidentKind;
  severity: "critical" | "warning";
  status: "new" | "acknowledged" | "resolved";
  started_at: string;
  ended_at: string | null;
  confidence: number;
  zone_name?: string;
  note: string;
  demo: boolean;
  snapshot_url?: string | null;
}
export interface Zone {
  id: string;
  camera_id: string;
  name: string;
  points: [number, number][];
  enabled: boolean;
}
export interface Track {
  id: number;
  bbox: [number, number, number, number];
  helmet: boolean | null;
  vest: boolean | null;
  confidence: number;
  pose?: number[][];
  fall?: boolean;
}
export interface Frame {
  type: "frame";
  camera_id: string;
  timestamp: string;
  tracks: Track[];
  demo: boolean;
  fps: number;
  latency_ms: number;
}
export interface Summary {
  cameras: number;
  online: number;
  incidents: number;
  critical: number;
  open: number;
  compliance: number | null;
  people: number;
  checked: number;
  series: { hour: string; count: number }[];
  kinds: { kind: IncidentKind; count: number }[];
  demo: boolean;
}
export const KIND_LABELS: Record<IncidentKind, string> = {
  no_helmet: "Без защитной каски",
  no_vest: "Без сигнального жилета",
  zone: "Вход в опасную зону",
  fall: "Возможное падение",
};
export const KIND_SHORT: Record<IncidentKind, string> = {
  no_helmet: "Без каски",
  no_vest: "Без жилета",
  zone: "Опасная зона",
  fall: "Падение",
};
