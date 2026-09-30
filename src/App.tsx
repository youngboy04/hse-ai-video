import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Bell,
  Box,
  Building2,
  CalendarDays,
  Camera as CameraIcon,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Download,
  Expand,
  Eye,
  Grid2X2,
  HardHat,
  LayoutDashboard,
  LoaderCircle,
  MapPin,
  Plus,
  Radio,
  ScanLine,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  TriangleAlert,
  Trash2,
  Undo2,
  Users,
  Video,
  Wifi,
  X,
  Zap,
  ChartNoAxesCombined,
  LogIn,
  Server,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import { api, downloadReport, downloadClip } from "./api";
import { useUI } from "./store";
import type { Camera, Incident, Page, Summary, Zone } from "./types";
import { KIND_LABELS, KIND_SHORT } from "./types";
import CameraView from "./CameraView";
import ValidationPage from "./ValidationPage";
import VideoSamplePage from "./VideoSamplePage";

const nav: { id: Page; label: string; icon: typeof Shield }[] = [
  { id: "overview", label: "Обзор", icon: LayoutDashboard },
  { id: "cameras", label: "Камеры", icon: Video },
  { id: "incidents", label: "Инциденты", icon: TriangleAlert },
  { id: "zones", label: "Зоны безопасности", icon: ScanLine },
  { id: "analytics", label: "Аналитика", icon: ChartNoAxesCombined },
  { id: "validation", label: "Проверка модели", icon: CheckCheck },
  { id: "sample", label: "Тестовое видео", icon: Video },
  { id: "settings", label: "Настройки", icon: Settings },
];
const fmt = (date: string) =>
  new Date(date).toLocaleTimeString("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
const statusLabel = {
  new: "Новый",
  acknowledged: "В работе",
  resolved: "Закрыт",
};
function IconKind({
  kind,
  size = 17,
}: {
  kind: Incident["kind"];
  size?: number;
}) {
  return kind === "no_helmet" ? (
    <HardHat size={size} />
  ) : kind === "zone" ? (
    <ScanLine size={size} />
  ) : kind === "fall" ? (
    <Activity size={size} />
  ) : (
    <Shield size={size} />
  );
}

export default function App() {
  const { page, setPage, toast, notify, token } = useUI();
  const [cameras, setCameras] = useState<Camera[]>([]),
    [incidents, setIncidents] = useState<Incident[]>([]),
    [zones, setZones] = useState<Zone[]>([]),
    [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [days, setDays] = useState(1),
    [site, setSite] = useState("all"),
    [query, setQuery] = useState(""),
    [overlays, setOverlays] = useState(true),
    [status, setStatus] = useState("all");
  const [modal, setModal] = useState<"camera" | "help" | null>(null),
    [selected, setSelected] = useState<Incident | null>(null),
    [expanded, setExpanded] = useState<Camera | null>(null),
    [notifications, setNotifications] = useState(false),
    [compact, setCompact] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const [c, i, z, s] = await Promise.all([
        api<Camera[]>("/cameras"),
        api<Incident[]>(`/incidents?days=${days}&limit=1000`),
        api<Zone[]>("/zones"),
        api<Summary>(`/summary?days=${days}&site=${encodeURIComponent(site)}`),
      ]);
      setCameras(c);
      setIncidents(i);
      setZones(z);
      setSummary(s);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [days, token, site]);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);
  const filteredCameras = cameras.filter(
    (c) =>
      (site === "all" || c.location.startsWith(site)) &&
      `${c.name} ${c.location}`.toLowerCase().includes(query.toLowerCase()),
  );
  const filteredIncidents = incidents.filter(
    (i) =>
      (status === "all" || i.status === status) &&
      (site === "all" ||
        cameras.find((c) => c.id === i.camera_id)?.location.startsWith(site)) &&
      `${i.camera_name} ${KIND_LABELS[i.kind]} ${i.track_id}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const exportReport = async () => {
    try {
      await downloadReport(days, site);
      notify("Отчёт CSV сохранён");
    } catch (e) {
      notify((e as Error).message);
    }
  };
  const toggleCamera = async (c: Camera) => {
    try {
      await api(`/cameras/${c.id}?enabled=${!c.enabled}`, { method: "PATCH" });
      await refresh();
      notify(c.enabled ? "Камера приостановлена" : "Камера включена");
    } catch (e) {
      notify((e as Error).message);
    }
  };
  const pageTitle = {
    overview: "Центр безопасности",
    cameras: "Видеомониторинг",
    incidents: "Журнал инцидентов",
    zones: "Зоны безопасности",
    analytics: "Аналитика безопасности",
    validation: "Проверка модели",
    sample: "Тестовое видео",
    settings: "Настройки системы",
  }[page];
  return (
    <div className={`app ${compact ? "sidebar-compact" : ""}`}>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("overview");
          }}
        >
          <span className="brand-icon">
            <ShieldCheck size={25} />
          </span>
          <span>
            HSE<span className="brand-ai"> AI</span>
            <small>ВИДЕОАНАЛИТИКА БЕЗОПАСНОСТИ</small>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">
            <Building2 size={19} />
          </span>
          <div>
            <strong>Промышленный объект</strong>
            <span>Единый центр мониторинга</span>
          </div>
          <ChevronDown size={14} />
        </div>
        <p className="nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</p>
        <nav>
          {nav.map(({ id, label, icon: Icon }) => (
            <button
              className={`nav-item ${page === id ? "active" : ""}`}
              key={id}
              aria-label={label}
              onClick={() => {
                setPage(id);
                setQuery("");
                setStatus("all");
              }}
            >
              <Icon size={19} />
              <span>{label}</span>
              {id === "incidents" && !!summary?.open && <b>{summary.open}</b>}
              {page === id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="edge-card">
            <div>
              <span className="dot green" /> Локальный контур{" "}
              <Shield size={14} />
            </div>
            <p>
              Данные под вашим контролем.
              <br />
              Обработка на вашем сервере.
            </p>
            <span>
              HSE AI-Video <b>v0.1 MVP</b>
            </span>
          </div>
          <button className="help-button" onClick={() => setModal("help")}>
            <CircleHelp size={18} />
            <span>Помощь и документация</span>
            <ArrowRight size={15} />
          </button>
          <div className="profile">
            <div className="avatar">ОП</div>
            <div>
              <strong>Оператор</strong>
              <span>Пульт безопасности</span>
            </div>
            <button
              title="Настройки доступа"
              onClick={() => setPage("settings")}
            >
              <Settings size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button collapse-button"
              title="Свернуть меню"
              onClick={() => setCompact(!compact)}
            >
              <Grid2X2 size={18} />
            </button>
            <span>Рабочее пространство</span>
            <ChevronRight size={13} />
            <strong>{nav.find((n) => n.id === page)?.label}</strong>
          </div>
          <div className="topbar-right">
            <span className="system-status">
              <span className={`dot ${error ? "red" : "green"}`} />
              {error ? "Нет соединения" : "Система на связи"}
            </span>
            <span className="top-divider" />
            <button
              className={`icon-button notification-button ${notifications ? "selected" : ""}`}
              title="Уведомления"
              onClick={() => setNotifications(!notifications)}
            >
              <Bell size={19} />
              {incidents.some((i) => i.status === "new") && <i />}
            </button>
            <div className="mini-avatar">ОП</div>
          </div>
          {notifications && (
            <div className="notification-popover">
              <div className="section-heading">
                <h3>Новые уведомления</h3>
                <button
                  className="icon-button"
                  onClick={() => setNotifications(false)}
                  aria-label="Закрыть уведомления"
                >
                  <X size={16} />
                </button>
              </div>
              {incidents
                .filter((i) => i.status === "new")
                .slice(0, 4)
                .map((i) => (
                  <button
                    className="notification-item"
                    key={i.id}
                    onClick={() => {
                      setSelected(i);
                      setNotifications(false);
                    }}
                  >
                    <span className={`event-icon ${i.severity}`}>
                      <IconKind kind={i.kind} />
                    </span>
                    <span>
                      <strong>{KIND_SHORT[i.kind]}</strong>
                      <small>
                        {i.camera_name} · {fmt(i.started_at)}
                      </small>
                    </span>
                  </button>
                ))}
              {!incidents.some((i) => i.status === "new") && (
                <p className="muted">Новых уведомлений нет</p>
              )}
            </div>
          )}
        </header>
        <main>
          <div className="page-heading">
            <div>
              <h1>{pageTitle}</h1>
            </div>
            {page !== "sample" && page !== "validation" && <div className="heading-actions">
              <button className="button" onClick={() => void exportReport()}>
                <Download size={16} /> Экспорт отчёта
              </button>
              <button
                className="button primary"
                onClick={() => setModal("camera")}
              >
                <Plus size={17} /> Добавить камеру
              </button>
            </div>}
          </div>
          {error && (
            <div className="error-banner">
              <TriangleAlert size={19} />
              <span>
                {error}.{" "}
                {error.includes("ключ")
                  ? "Откройте настройки подключения."
                  : "Проверьте, запущен ли Backend на порту 8000."}
              </span>
              <button onClick={() => setPage("settings")}>Настройки</button>
              <button onClick={() => void refresh()}>Повторить</button>
            </div>
          )}
          {summary?.demo && page !== "sample" && page !== "validation" && (
            <div className="demo-banner">
              <span>
                <Box size={14} /> Демонстрационное пространство
              </span>
              <p>
                Синтетические потоки и тестовые инциденты. Реальные камеры
                подключаются отдельно.
              </p>
              <button onClick={() => setModal("help")}>
                Подробнее <ArrowRight size={13} />
              </button>
            </div>
          )}
          {page !== "settings" && page !== "sample" && page !== "validation" && (
            <div className="filterbar">
              <div className="filter-left">
                <label className="select-wrap">
                  <Building2 size={15} />
                  <select
                    aria-label="Корпус"
                    value={site}
                    onChange={(e) => setSite(e.target.value)}
                  >
                    <option value="all">Все корпуса</option>
                    {Array.from(
                      new Set(cameras.map((c) => c.location.split(" · ")[0])),
                    ).map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                  <ChevronDown size={13} />
                </label>
                <span className="filter-divider" />
                <span className="last-updated">
                  <span className="dot green" /> Обновление каждые 5 сек
                </span>
              </div>
              <label className="select-wrap date-select">
                <CalendarDays size={15} />
                <select
                  aria-label="Период отчёта"
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                >
                  <option value={1}>Последние 24 часа</option>
                  <option value={7}>Последние 7 дней</option>
                  <option value={30}>Последние 30 дней</option>
                </select>
                <ChevronDown size={13} />
              </label>
            </div>
          )}
          {loading && !summary && (
            <div className="loading-state">
              <LoaderCircle className="spin" />
              Подключение к платформе…
            </div>
          )}
          {page === "overview" && (
            <>
              <Stats summary={summary} />
              <div className="monitor-layout">
                <section className="panel monitor-panel">
                  <div className="section-heading">
                    <div className="title-with-count">
                      <h2>Мониторинг в реальном времени</h2>
                      <span className="count-tag">
                        {filteredCameras.length}
                      </span>
                    </div>
                    <div className="section-tools">
                      <button
                        className={`overlay-toggle ${overlays ? "on" : ""}`}
                        onClick={() => setOverlays(!overlays)}
                        aria-pressed={overlays}
                      >
                        <ScanLine size={15} />
                        Разметка <span />
                      </button>
                      <span className="divider" />
                      <button
                        className="icon-button"
                        title="Все камеры"
                        onClick={() => setPage("cameras")}
                      >
                        <Expand size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="camera-grid">
                    {filteredCameras.slice(0, 4).map((c) => (
                      <CameraCard
                        key={c.id}
                        camera={c}
                        zones={zones}
                        overlays={overlays}
                        onExpand={() => setExpanded(c)}
                      />
                    ))}
                    {!filteredCameras.length && !loading && (
                      <Empty
                        icon={<Video size={28} />}
                        title="Камеры не найдены"
                        text="Добавьте камеру или выберите другой корпус."
                      />
                    )}
                  </div>
                  <div className="panel-foot">
                    <span>
                      <span className="dot green" /> {summary?.online || 0}{" "}
                      камер в сети <span className="foot-separator">/</span>{" "}
                      {summary?.people || 0} человек в кадре
                    </span>
                    <button onClick={() => setPage("cameras")}>
                      Открыть все камеры <ArrowRight size={14} />
                    </button>
                  </div>
                </section>
                <section className="panel live-events">
                  <div className="section-heading">
                    <h2>Лента событий</h2>
                    <span className="live-pill">
                      <span className="dot red" /> LIVE
                    </span>
                  </div>
                  <div className="event-feed">
                    {filteredIncidents.slice(0, 5).map((i) => (
                      <EventItem
                        key={i.id}
                        incident={i}
                        onClick={() => setSelected(i)}
                      />
                    ))}
                    {!filteredIncidents.length && (
                      <Empty
                        icon={<ShieldCheck size={26} />}
                        title="Нарушений не обнаружено"
                        text="Новые события появятся здесь."
                      />
                    )}
                  </div>
                  <button
                    className="feed-all"
                    onClick={() => setPage("incidents")}
                  >
                    Все инциденты <ArrowRight size={15} />
                  </button>
                </section>
              </div>
              <div className="insights-grid">
                <section className="panel trend-panel">
                  <div className="section-heading">
                    <div>
                      <h2>Динамика инцидентов</h2>
                      <p>Количество событий за последние 12 часов</p>
                    </div>
                    <span className="chart-legend">
                      <i /> Инциденты
                    </span>
                  </div>
                  <Trend summary={summary} />
                </section>
                <section className="panel safety-panel">
                  <div className="section-heading">
                    <h2>Контроль безопасности</h2>
                    <ShieldCheck size={19} className="muted" />
                  </div>
                  <div className="safety-content">
                    <div
                      className="compliance-ring"
                      style={
                        {
                          "--progress": `${summary?.compliance || 0}%`,
                        } as React.CSSProperties
                      }
                    >
                      <div>
                        <strong>
                          {summary?.compliance == null
                            ? "—"
                            : Math.round(summary.compliance)}
                          <small>%</small>
                        </strong>
                        <span>соблюдение СИЗ</span>
                      </div>
                    </div>
                    <div className="safety-legend">
                      <p>
                        <i className="green-bg" />
                        СИЗ проверены{" "}
                        <strong>{summary?.checked || 0} чел.</strong>
                      </p>
                      <p>
                        <i className="amber-bg" />
                        Требуют внимания <strong>{summary?.open || 0}</strong>
                      </p>
                      <p>
                        <i className="blue-bg" />
                        Зоны контроля{" "}
                        <strong>{zones.filter((z) => z.enabled).length}</strong>
                      </p>
                      <span>По текущим распознанным трекам</span>
                    </div>
                  </div>
                </section>
              </div>
              <section className="panel">
                <div className="section-heading">
                  <h2>Последние инциденты</h2>
                  <button
                    className="text-button"
                    onClick={() => setPage("incidents")}
                  >
                    Открыть журнал <ArrowRight size={14} />
                  </button>
                </div>
                <IncidentTable
                  incidents={filteredIncidents.slice(0, 5)}
                  onSelect={setSelected}
                />
              </section>
            </>
          )}
          {page === "cameras" && (
            <>
              <div className="content-toolbar">
                <div className="tab-group">
                  <button className="active">
                    Все камеры <span>{filteredCameras.length}</span>
                  </button>
                </div>
                <SearchBox
                  value={query}
                  onChange={setQuery}
                  placeholder="Название или расположение"
                />
              </div>
              <div className="camera-grid full-camera-grid">
                {filteredCameras.map((c) => (
                  <CameraCard
                    key={c.id}
                    camera={c}
                    zones={zones}
                    overlays={overlays}
                    onExpand={() => setExpanded(c)}
                    onToggle={() => void toggleCamera(c)}
                  />
                ))}
                <button
                  className="add-camera-tile"
                  onClick={() => setModal("camera")}
                >
                  <span>
                    <Plus size={25} />
                  </span>
                  <strong>Подключить камеру</strong>
                  <small>RTSP-поток или демонстрационный источник</small>
                </button>
              </div>
            </>
          )}
          {page === "incidents" && (
            <section className="panel">
              <div className="content-toolbar padded">
                <div className="tab-group">
                  {[
                    ["all", "Все события"],
                    ["new", "Новые"],
                    ["acknowledged", "В работе"],
                    ["resolved", "Закрытые"],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      className={status === key ? "active" : ""}
                      onClick={() => setStatus(key)}
                    >
                      {label}
                      <span>
                        {
                          incidents.filter(
                            (i) => key === "all" || i.status === key,
                          ).length
                        }
                      </span>
                    </button>
                  ))}
                </div>
                <SearchBox
                  value={query}
                  onChange={setQuery}
                  placeholder="Камера, тип или ID трека"
                />
              </div>
              <IncidentTable
                incidents={filteredIncidents}
                onSelect={setSelected}
              />
              <div className="panel-foot">
                <span>
                  Показано {filteredIncidents.length} событий · до 1 000
                  последних
                </span>
                <button onClick={() => void exportReport()}>
                  <ArrowDownToLine size={14} /> Полная выгрузка CSV
                </button>
              </div>
            </section>
          )}
          {page === "zones" && (
            <ZoneEditor cameras={cameras} zones={zones} refresh={refresh} />
          )}
          {page === "analytics" && (
            <>
              <Stats summary={summary} />
              <div className="analytics-grid">
                <section className="panel">
                  <div className="section-heading">
                    <div>
                      <h2>События по времени</h2>
                      <p>Последние 12 часов · локальное время</p>
                    </div>
                    <Activity size={19} className="muted" />
                  </div>
                  <Trend summary={summary} height={300} />
                </section>
                <section className="panel">
                  <div className="section-heading">
                    <h2>Типы нарушений</h2>
                    <span className="count-tag">{summary?.incidents || 0}</span>
                  </div>
                  <div style={{ height: 300, padding: "15px 20px" }}>
                    <ResponsiveContainer>
                      <BarChart
                        data={
                          summary?.kinds.map((k) => ({
                            ...k,
                            name: KIND_SHORT[k.kind],
                          })) || []
                        }
                        layout="vertical"
                        margin={{ left: 0, right: 25 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          horizontal={false}
                          stroke="#edf0f3"
                        />
                        <XAxis
                          type="number"
                          allowDecimals={false}
                          tick={{ fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={100}
                          tick={{ fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip cursor={{ fill: "#f3f7f8" }} />
                        <Bar
                          isAnimationActive={false}
                          dataKey="count"
                          name="Инциденты"
                          radius={[0, 5, 5, 0]}
                          barSize={25}
                        >
                          {summary?.kinds.map((k, i) => (
                            <Cell
                              key={k.kind}
                              fill={
                                ["#20b59e", "#f3b653", "#7281cb", "#ed7f7f"][
                                  i % 4
                                ]
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </section>
              </div>
              <div className="info-strip">
                <ShieldCheck size={23} />
                <div>
                  <strong>Прозрачная методика расчёта</strong>
                  <p>
                    Один инцидент — одно непрерывное нарушение. Соблюдение СИЗ
                    рассчитывается только по трекам с известным результатом
                    проверки каски и жилета. Точность моделей и экономический
                    эффект требуют отдельной валидации.
                  </p>
                </div>
              </div>
            </>
          )}
          {page === "settings" && <SettingsPage />}
          {page === "validation" && <ValidationPage />}
          {page === "sample" && <VideoSamplePage />}
          <footer className="page-footer">
            <span>
              HSE AI-Video
            </span>
            <span>
              <ShieldCheck size={13} /> Обработка в локальном контуре
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCheck size={18} />
          {toast}
        </div>
      )}
      {modal === "camera" && (
        <Modal
          title="Подключение камеры"
          onClose={() => setModal(null)}
        >
          <CameraForm
            onDone={async () => {
              setModal(null);
              await refresh();
              notify("Камера добавлена");
            }}
          />
        </Modal>
      )}
      {modal === "help" && (
        <Modal
          title="HSE AI-Video · MVP"
          subtitle="О платформе и демонстрационном режиме"
          onClose={() => setModal(null)}
        >
          <div className="help-content">
            <span className="help-hero">
              <ShieldCheck size={36} />
            </span>
            <h3>Работа с камерами и событиями</h3>
            <p>
              Платформа объединяет камеры, контроль СИЗ и опасных зон. В
              деморежиме сцены и треки синтетические, а журнал и обработка
              инцидентов работают через настоящий API.
            </p>
            <ol>
              <li>Подключите RTSP-камеру на странице «Камеры».</li>
              <li>Задайте полигон на странице «Зоны безопасности».</li>
              <li>Установите проверенные ONNX-модели на сервер инференса.</li>
              <li>Обрабатывайте события и выгружайте отчёты.</li>
            </ol>
            <div className="info-note">
              Инструкции запуска и контракты моделей находятся в README проекта.
              Учётные данные камеры не передаются в интерфейс.
            </div>
            <a
              className="button"
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
            >
              Документация API <ArrowRight size={15} />
            </a>
          </div>
        </Modal>
      )}
      {expanded && (
        <Modal
          title={expanded.name}
          subtitle={`${expanded.location} · ${expanded.demo ? "Демонстрационный источник" : "RTSP"}`}
          wide
          onClose={() => setExpanded(null)}
        >
          <CameraView
            camera={cameras.find((c) => c.id === expanded.id) || expanded}
            zones={zones}
            overlays={overlays}
            large
          />
          <div className="expanded-foot">
            <span>
              <span className="dot green" /> Трекинг и контроль зон
            </span>
            <button className="button" onClick={() => setOverlays(!overlays)}>
              <Eye size={15} />
              {overlays ? "Скрыть" : "Показать"} разметку
            </button>
          </div>
        </Modal>
      )}
      {selected && (
        <IncidentModal
          incident={selected}
          onClose={() => setSelected(null)}
          onUpdate={async (updated) => {
            setSelected(updated);
            await refresh();
          }}
        />
      )}
    </div>
  );
}

function Stats({ summary: s }: { summary: Summary | null }) {
  const stats = [
    {
      label: "Камеры в сети",
      value: s ? `${s.online}` : "—",
      suffix: s ? `/ ${s.cameras}` : "",
      icon: Video,
      color: "teal",
      foot: "Подключённые видеопотоки",
      tag: "Мониторинг",
      tagIcon: Radio,
    },
    {
      label: "Инциденты за период",
      value: s?.incidents ?? "—",
      suffix: "",
      icon: TriangleAlert,
      color: "orange",
      foot: s ? `${s.critical} требуют особого внимания` : "История событий",
      tag: "Контроль",
      tagIcon: Activity,
    },
    {
      label: "Соблюдение СИЗ",
      value: s?.compliance == null ? "—" : s.compliance.toFixed(1),
      suffix: s?.compliance == null ? "" : "%",
      icon: ShieldCheck,
      color: "purple",
      foot: "По текущим распознанным трекам",
      tag: "СИЗ",
      tagIcon: Check,
    },
    {
      label: "Людей в кадре",
      value: s?.people ?? "—",
      suffix: "",
      icon: Users,
      color: "blue",
      foot: "Сумма треков со всех камер",
      tag: "Сейчас",
      tagIcon: Clock3,
    },
  ];
  return (
    <div className="stats-grid">
      {stats.map(
        ({
          label,
          value,
          suffix,
          icon: Icon,
          color,
          foot,
          tag,
          tagIcon: TagIcon,
        }) => (
          <div className="stat-card" key={label}>
            <div className="stat-head">
              <span>{label}</span>
              <span className={`stat-icon ${color}`}>
                <Icon size={19} />
              </span>
            </div>
            <div className="stat-value">
              {value}
              <span>{suffix}</span>
              <span className={`stat-tag ${color}`}>
                <TagIcon size={11} />
                {tag}
              </span>
            </div>
            <p>{foot}</p>
          </div>
        ),
      )}
    </div>
  );
}
function CameraCard({
  camera,
  zones,
  overlays,
  onExpand,
  onToggle,
}: {
  camera: Camera;
  zones: Zone[];
  overlays: boolean;
  onExpand: () => void;
  onToggle?: () => void;
}) {
  return (
    <article className="camera-card">
      <CameraView
        camera={camera}
        zones={zones}
        overlays={overlays}
        onExpand={onExpand}
      />
      <div className="camera-info">
        <div>
          <button className="camera-title" onClick={onExpand}>
            {camera.name}
          </button>
          <p>
            <MapPin size={11} />
            {camera.location}
          </p>
        </div>
        {onToggle ? (
          <button
            className={`button small ${camera.enabled ? "" : "primary"}`}
            onClick={onToggle}
          >
            {camera.enabled ? "Остановить" : "Включить"}
          </button>
        ) : (
          <span className={`camera-fps ${camera.online ? "" : "muted"}`}>
            <span className={`dot ${camera.online ? "green" : "gray"}`} />
            {camera.online ? `${camera.fps} FPS` : "Офлайн"}
          </span>
        )}
      </div>
    </article>
  );
}
function EventItem({
  incident: i,
  onClick,
}: {
  incident: Incident;
  onClick: () => void;
}) {
  return (
    <button className="event-item" onClick={onClick}>
      <span className={`event-icon ${i.severity}`}>
        <IconKind kind={i.kind} />
      </span>
      <div>
        <div className="event-title">
          <strong>{KIND_SHORT[i.kind]}</strong>
          <span>{fmt(i.started_at).slice(0, 5)}</span>
        </div>
        <p>{i.camera_name}</p>
        <div className="event-meta">
          <span>ID #{i.track_id}</span>
          <span className={`severity-label ${i.severity}`}>
            {i.severity === "critical" ? "Критический" : "Внимание"}
          </span>
        </div>
      </div>
    </button>
  );
}
function Trend({
  summary,
  height = 180,
}: {
  summary: Summary | null;
  height?: number;
}) {
  return (
    <div className="trend-chart" style={{ height }}>
      <ResponsiveContainer>
        <AreaChart
          data={
            summary?.series.map((s) => ({
              ...s,
              hour: new Date(s.hour).toLocaleTimeString("ru-RU", {
                hour: "2-digit",
                minute: "2-digit",
              }),
            })) || []
          }
          margin={{ top: 10, right: 22, left: -22, bottom: 0 }}
        >
          <defs>
            <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#18b49a" stopOpacity={0.23} />
              <stop offset="100%" stopColor="#18b49a" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 4"
            stroke="#eaf0f2"
            vertical={false}
          />
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 10, fill: "#8b96a5" }}
            axisLine={false}
            tickLine={false}
            minTickGap={30}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 10, fill: "#8b96a5" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              border: "1px solid #e5e9ed",
              borderRadius: 10,
              fontSize: 12,
            }}
          />
          <Area
            isAnimationActive={false}
            dataKey="count"
            name="Инциденты"
            type="monotone"
            stroke="#18af98"
            strokeWidth={2.3}
            fill="url(#trend-fill)"
            activeDot={{ r: 5, stroke: "white", strokeWidth: 3 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
function IncidentTable({
  incidents,
  onSelect,
}: {
  incidents: Incident[];
  onSelect: (i: Incident) => void;
}) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [incidents.length]);
  const rows = incidents.slice(page * 12, page * 12 + 12);
  return (
    <>
      {incidents.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>СОБЫТИЕ</th>
                <th>КАМЕРА / УЧАСТОК</th>
                <th>ВРЕМЯ</th>
                <th>ТРЕК</th>
                <th>СТАТУС</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((i) => (
                <tr key={i.id} onClick={() => onSelect(i)}>
                  <td>
                    <div className="table-event">
                      <span className={`event-icon mini ${i.severity}`}>
                        <IconKind kind={i.kind} size={15} />
                      </span>
                      <span>
                        {KIND_LABELS[i.kind]}
                        {i.demo && <small>Демонстрация</small>}
                      </span>
                    </div>
                  </td>
                  <td>{i.camera_name}</td>
                  <td className="tabular">
                    {fmt(i.started_at)}
                    <small>
                      {new Date(i.started_at).toLocaleDateString("ru-RU")}
                    </small>
                  </td>
                  <td>
                    <span className="track-tag">#{i.track_id}</span>
                  </td>
                  <td>
                    <span className={`status-tag ${i.status}`}>
                      <i />
                      {statusLabel[i.status]}
                    </span>
                  </td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Открыть инцидент ${i.id}`}
                    >
                      <ChevronRight size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          icon={<ShieldCheck size={27} />}
          title="Событий не найдено"
          text="Попробуйте изменить фильтры или период."
        />
      )}
      {incidents.length > 12 && (
        <div className="pagination">
          <span>
            {page * 12 + 1}–{Math.min((page + 1) * 12, incidents.length)} из{" "}
            {incidents.length}
          </span>
          <button
            className="icon-button"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            aria-label="Предыдущая страница"
          >
            <ChevronLeft size={17} />
          </button>
          <button
            className="icon-button"
            disabled={(page + 1) * 12 >= incidents.length}
            onClick={() => setPage(page + 1)}
            aria-label="Следующая страница"
          >
            <ChevronRight size={17} />
          </button>
        </div>
      )}
    </>
  );
}
function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (s: string) => void;
  placeholder: string;
}) {
  return (
    <label className="search-box">
      <Search size={16} />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
      {value && (
        <button onClick={() => onChange("")} aria-label="Очистить поиск">
          <X size={14} />
        </button>
      )}
    </label>
  );
}
function Empty({
  icon,
  title,
  text,
}: {
  icon: ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="empty-state">
      {icon}
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}
function Modal({
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null),
    close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close.current();
      if (e.key === "Tab") {
        const nodes = ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),input,select,textarea,a[href],[tabindex="0"]',
        );
        if (!nodes?.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-header">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Закрыть"
          >
            <X size={21} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
function CameraForm({ onDone }: { onDone: () => Promise<void> }) {
  const [name, setName] = useState(""),
    [location, setLocation] = useState(""),
    [source, setSource] = useState(""),
    [demo, setDemo] = useState(false),
    [saving, setSaving] = useState(false),
    [error, setError] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api("/cameras", {
        method: "POST",
        body: JSON.stringify({
          name,
          location,
          source: demo ? "demo" : source,
          enabled: true,
        }),
      });
      await onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <form onSubmit={(e) => void submit(e)} className="form">
      <label>
        Название камеры
        <input
          required
          minLength={2}
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например, Сборочный участок № 2"
        />
      </label>
      <label>
        Расположение
        <input
          required
          minLength={2}
          maxLength={100}
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Корпус А · Участок 02"
        />
      </label>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={demo}
          onChange={(e) => setDemo(e.target.checked)}
        />{" "}
        Использовать демонстрационный источник
      </label>
      {!demo && (
        <label>
          RTSP-адрес
          <input
            required
            value={source}
            onChange={(e) => setSource(e.target.value)}
            type="password"
            autoComplete="off"
            placeholder="rtsp://user:password@192.168.1.10:554/stream"
          />
          <small>
            Адрес хранится на локальном сервере. Пароль не возвращается в
            интерфейс.
          </small>
        </label>
      )}
      <div className="info-note">
        <Wifi size={17} />
        {demo
          ? "Синтетический поток для знакомства с платформой."
          : "Камера должна быть доступна сервису захвата. Для анализа необходимы ONNX-модели."}
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full-width" disabled={saving}>
        {saving ? (
          <LoaderCircle className="spin" size={16} />
        ) : (
          <Plus size={16} />
        )}
        Добавить камеру
      </button>
    </form>
  );
}
function IncidentModal({
  incident: i,
  onClose,
  onUpdate,
}: {
  incident: Incident;
  onClose: () => void;
  onUpdate: (i: Incident) => Promise<void>;
}) {
  const [note, setNote] = useState(i.note),
    [saving, setSaving] = useState(false),
    [image, setImage] = useState("");
  const notify = useUI((s) => s.notify),
    token = useUI((s) => s.token);
  useEffect(() => {
    let url = "",
      disposed = false;
    if (i.snapshot_url)
      fetch(i.snapshot_url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((r) => {
          if (!r.ok) throw new Error();
          return r.blob();
        })
        .then((b) => {
          if (!disposed) {
            url = URL.createObjectURL(b);
            setImage(url);
          }
        })
        .catch(() => notify("Снимок недоступен"));
    return () => {
      disposed = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [i.snapshot_url, token, notify]);
  const save = async (status: Incident["status"]) => {
    setSaving(true);
    try {
      const updated = await api<Incident>(`/incidents/${i.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status, note }),
      });
      await onUpdate(updated);
      notify("Инцидент обновлён");
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  const seconds = i.ended_at
    ? Math.max(
        0,
        Math.round((+new Date(i.ended_at) - +new Date(i.started_at)) / 1000),
      )
    : null;
  return (
    <Modal
      title={KIND_LABELS[i.kind]}
      subtitle={`${i.camera_name} · Трек #${i.track_id}`}
      onClose={onClose}
    >
      <div className="incident-detail">
        <div className="detail-badges">
          <span className={`status-tag ${i.status}`}>
            <i />
            {statusLabel[i.status]}
          </span>
          <span className={`severity-label ${i.severity}`}>
            {i.severity === "critical" ? "Критический" : "Внимание"}
          </span>
          {i.demo && <span className="count-tag">Демонстрация</span>}
        </div>
        {image ? (
          <img
            className="snapshot"
            src={image}
            alt="Кадр в момент регистрации нарушения"
          />
        ) : (
          <div className="evidence-placeholder">
            <CameraIcon size={30} />
            <strong>
              {i.demo
                ? "Синтетический тестовый инцидент"
                : "Снимок не сохранён"}
            </strong>
            <span>
              {i.demo
                ? "Это пример события, а не запись с реальной камеры."
                : "Медиафайл для этого события отсутствует."}
            </span>
          </div>
        )}
        <dl className="detail-grid">
          <div>
            <dt>Начало нарушения</dt>
            <dd>{new Date(i.started_at).toLocaleString("ru-RU")}</dd>
          </div>
          <div>
            <dt>Длительность наблюдения</dt>
            <dd>
              {seconds === null ? "Нарушение продолжается" : `${seconds} сек`}
            </dd>
          </div>
          <div>
            <dt>Уверенность модели</dt>
            <dd>{Math.round(i.confidence * 100)}%</dd>
          </div>
          <div>
            <dt>Опасная зона</dt>
            <dd>{i.zone_name || "Не указана"}</dd>
          </div>
        </dl>
        <label className="form-label">
          Комментарий оператора
          <textarea
            rows={3}
            maxLength={2000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Результат проверки и принятые меры…"
          />
        </label>
        <div className="modal-actions">
          {!i.demo && (
            <button
              className="button"
              onClick={() =>
                void downloadClip(i.id).catch((e) => notify(e.message))
              }
            >
              <Download size={15} />
              Клип
            </button>
          )}
          <button
            className="button"
            disabled={saving}
            onClick={() => void save(i.status)}
          >
            Сохранить
          </button>
          {i.status === "new" && (
            <button
              className="button"
              disabled={saving}
              onClick={() => void save("acknowledged")}
            >
              Взять в работу
            </button>
          )}
          {i.status !== "resolved" && (
            <button
              className="button primary"
              disabled={saving}
              onClick={() => void save("resolved")}
            >
              <Check size={16} />
              Закрыть инцидент
            </button>
          )}
        </div>
        <p className="detail-hint">
          Закрытие оператором не останавливает наблюдение за нарушением.
        </p>
      </div>
    </Modal>
  );
}
function ZoneEditor({
  cameras,
  zones,
  refresh,
}: {
  cameras: Camera[];
  zones: Zone[];
  refresh: () => Promise<void>;
}) {
  const [id, setId] = useState(cameras[0]?.id || ""),
    [points, setPoints] = useState<[number, number][]>([]),
    [name, setName] = useState(""),
    [saving, setSaving] = useState(false),
    [deleting, setDeleting] = useState<string | null>(null);
  const notify = useUI((s) => s.notify);
  useEffect(() => {
    if (!id && cameras.length) setId(cameras[0].id);
  }, [cameras, id]);
  const camera = cameras.find((c) => c.id === id);
  const save = async () => {
    setSaving(true);
    try {
      await api("/zones", {
        method: "POST",
        body: JSON.stringify({ camera_id: id, name, points, enabled: true }),
      });
      setPoints([]);
      setName("");
      await refresh();
      notify("Зона контроля создана");
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  const remove = async (zone: string) => {
    try {
      await api(`/zones/${zone}`, { method: "DELETE" });
      setDeleting(null);
      await refresh();
      notify("Зона удалена");
    } catch (e) {
      notify((e as Error).message);
    }
  };
  return (
    <div className="zone-layout">
      <section className="panel zone-editor">
        <div className="section-heading">
          <h2>Редактор зон</h2>
          <select
            aria-label="Камера для зоны"
            value={id}
            onChange={(e) => {
              setId(e.target.value);
              setPoints([]);
            }}
          >
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        {camera ? (
          <CameraView
            camera={camera}
            zones={zones}
            large
            draft={points}
            onPoint={(point) => {
              if (points.length < 32) setPoints([...points, point]);
            }}
          />
        ) : (
          <Empty
            icon={<Video size={25} />}
            title="Добавьте камеру"
            text="Для создания зоны требуется источник видео."
          />
        )}
        <div className="zone-instructions">
          <span>
            <ScanLine size={17} /> Нажимайте на изображение, чтобы задать
            вершины полигона.
          </span>
          <span>{points.length} / 32 точек</span>
        </div>
        <div className="zone-actions">
          <button
            className="button"
            disabled={!points.length}
            onClick={() => setPoints(points.slice(0, -1))}
          >
            <Undo2 size={15} />
            Отменить точку
          </button>
          <button
            className="button"
            disabled={!points.length}
            onClick={() => setPoints([])}
          >
            <Trash2 size={15} />
            Очистить
          </button>
        </div>
        <div className="zone-save">
          <input
            aria-label="Название зоны"
            placeholder="Название опасной зоны"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            className="button primary"
            disabled={points.length < 3 || name.trim().length < 2 || saving}
            onClick={() => void save()}
          >
            <Plus size={15} />
            Сохранить зону
          </button>
        </div>
        <p className="detail-hint">
          Событие фиксируется, когда точка у ног человека остаётся внутри зоны
          более заданного времени.
        </p>
      </section>
      <section className="panel zone-list">
        <div className="section-heading">
          <h2>Зоны камеры</h2>
          <span className="count-tag">
            {zones.filter((z) => z.camera_id === id).length}
          </span>
        </div>
        {zones
          .filter((z) => z.camera_id === id)
          .map((z) => (
            <div className="zone-list-item" key={z.id}>
              <span className="zone-icon">
                <ScanLine size={19} />
              </span>
              <div>
                <strong>{z.name}</strong>
                <p>
                  {z.points.length} вершин ·{" "}
                  {z.enabled ? "Контроль активен" : "Отключена"}
                </p>
                {deleting === z.id && (
                  <div className="delete-confirm">
                    <button onClick={() => void remove(z.id)}>
                      Удалить зону
                    </button>
                    <button onClick={() => setDeleting(null)}>Отмена</button>
                  </div>
                )}
              </div>
              <button
                className="icon-button"
                title="Удалить зону"
                onClick={() => setDeleting(z.id)}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        {!zones.some((z) => z.camera_id === id) && (
          <Empty
            icon={<Square size={25} />}
            title="Зон пока нет"
            text="Нарисуйте первый полигон на изображении."
          />
        )}
        <div className="zone-tip">
          <Shield size={22} />
          <strong>Точность начинается с разметки</strong>
          <p>
            Выделяйте поверхность пола. Учитывайте перспективу камеры и
            оставляйте безопасный отступ от оборудования.
          </p>
        </div>
      </section>
    </div>
  );
}
interface SystemInfo {
  api: string;
  database: string;
  demo: boolean;
  inference: {
    status: string;
    provider?: string;
    models?: Record<string, boolean>;
  };
  redis_configured: boolean;
  pending_events: number;
  debounce_seconds: number;
  close_after_seconds: number;
  auth_enabled: boolean;
  version: string;
}
function SettingsPage() {
  const token = useUI((s) => s.token),
    setToken = useUI((s) => s.setToken),
    [draft, setDraft] = useState(token),
    [system, setSystem] = useState<SystemInfo | null>(null),
    [error, setError] = useState("");
  const notify = useUI((s) => s.notify);
  useEffect(() => {
    api<SystemInfo>("/system")
      .then(setSystem)
      .catch((e) => setError(e.message));
  }, [token]);
  return (
    <div className="settings-grid">
      <section className="panel settings-panel">
        <div className="section-heading">
          <h2>Состояние платформы</h2>
          <Server size={20} className="muted" />
        </div>
        {error && !system && <p className="form-error">{error}</p>}
        {[
          {
            name: "Backend API",
            value: system ? "Доступен" : "Нет соединения",
            ok: !!system,
          },
          { name: "База данных", value: system?.database || "—", ok: !!system },
          {
            name: "Сервер инференса",
            value:
              system?.inference.status === "ready"
                ? "Модели загружены"
                : system?.inference.status === "unavailable"
                  ? "Не подключён"
                  : "Ожидает модели",
            ok: system?.inference.status === "ready",
          },
          {
            name: "Брокер Redis",
            value: system?.redis_configured
              ? `Настроен · в очереди ${system.pending_events}`
              : "Локальная SQL-очередь",
            ok: !!system?.redis_configured,
          },
          {
            name: "Авторизация",
            value: system?.auth_enabled
              ? "Ключ доступа включён"
              : "Локальный режим без ключа",
            ok: !!system?.auth_enabled,
          },
          {
            name: "Демонстрационный режим",
            value: system?.demo ? "Включён" : "Выключен",
            ok: !!system?.demo,
          },
        ].map((s) => (
          <div className="service-row" key={s.name}>
            <span>{s.name}</span>
            <strong>
              <span className={`dot ${s.ok ? "green" : "amber"}`} />
              {s.value}
            </strong>
          </div>
        ))}
        <div className="settings-note">
          Обработка моделей включается после установки весов в каталог{" "}
          <code>models/</code>. Параметры сервисов задаются через переменные
          окружения.
        </div>
      </section>
      <div className="settings-stack">
        <section className="panel settings-panel">
          <div className="section-heading">
            <h2>Доступ к серверу</h2>
            <LogIn size={18} className="muted" />
          </div>
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault();
              setToken(draft);
              setError("");
              notify("Настройки подключения сохранены");
            }}
          >
            <label>
              Ключ оператора
              <input
                type="password"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="OPERATOR_TOKEN"
                autoComplete="off"
              />
              <small>Хранится только в текущей сессии браузера.</small>
            </label>
            <button className="button primary">
              <Check size={16} />
              Сохранить подключение
            </button>
          </form>
        </section>
        <section className="panel settings-panel">
          <div className="section-heading">
            <h2>Правила агрегации</h2>
            <SlidersHorizontal size={18} className="muted" />
          </div>
          <div className="service-row">
            <span>Подтверждение нарушения</span>
            <strong>{system?.debounce_seconds ?? "—"} сек</strong>
          </div>
          <div className="service-row">
            <span>Завершение после потери трека</span>
            <strong>{system?.close_after_seconds ?? "—"} сек</strong>
          </div>
          <div className="info-note">
            <Zap size={17} />
            Временные пороги не зависят от FPS камеры.
          </div>
        </section>
      </div>
    </div>
  );
}
