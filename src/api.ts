import { useUI } from "./store";
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = useUI.getState().token;
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "Сервис недоступен" }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Ошибка запроса (${response.status})`,
    );
  }
  return response.json();
}
export async function downloadReport(period: number, site = "all") {
  const token = useUI.getState().token;
  const res = await fetch(
    `/api/incidents/export?days=${period}&site=${encodeURIComponent(site)}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!res.ok) throw new Error("Не удалось выгрузить отчёт");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `HSE-инциденты-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
export async function downloadClip(incidentId: string) {
  const token = useUI.getState().token;
  const response = await fetch(`/api/clips/${incidentId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok)
    throw new Error("Видеофрагмент ещё не сохранён или недоступен");
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `hse-${incidentId}.mp4`;
  a.click();
  URL.revokeObjectURL(url);
}
