import React, { useEffect, useMemo, useRef, useState } from "react";
import { request } from "./api";

type SourceId = "uisp" | "mikrotik" | "tauc";
type NetworkTab = "devices" | "alarms" | "sources";

type Device = {
  id: string;
  source_id: string;
  source: SourceId;
  source_label: string;
  name: string;
  model: string;
  type: string;
  status: "online" | "offline" | "warning" | "unknown";
  site_name: string;
  ip?: string | null;
  mac?: string | null;
  firmware?: string | null;
  cpu?: number | null;
  memory?: number | null;
  temperature?: number | null;
  signal?: number | null;
  latency?: number | null;
  packet_loss?: number | null;
  customer_count: number;
  interface_count?: number;
  client_id?: string;
  serial_number?: string;
  network_id?: string;
  wifi_networks?: number;
  warning_count?: number;
  poll_detail?: string;
  poll_mode: string;
  poll_interval_seconds?: number | null;
  last_polled_at?: string | null;
  cache_age_seconds?: number | null;
  cache_remaining_seconds?: number | null;
};

type Alarm = {
  severity: "critical" | "warning";
  type: string;
  title: string;
  detail: string;
  device_id: string;
  device_name: string;
  site_name: string;
  customers_affected: number;
  source: SourceId;
  source_label: string;
};

type PollSource = {
  id: SourceId;
  name: string;
  state: "online" | "degraded" | "offline" | "unconfigured";
  mode: string;
  device_count: number;
  poll_interval_seconds?: number | null;
  last_polled_at?: string | null;
  cache_age_seconds?: number | null;
  cached_devices?: number;
  detail: string;
};

type PollingOverview = {
  generated_at: string;
  poll_interval_seconds: number;
  mode: string;
  summary: {
    devices_total: number;
    devices_online: number;
    devices_offline: number;
    devices_warning: number;
    devices_unknown: number;
    sites_total: number;
    active_alarms: number;
    critical_alarms: number;
    customers_affected: number;
    sources_healthy: number;
    sources_total: number;
  };
  sources: PollSource[];
  devices: Device[];
  alarms: Alarm[];
  sites: string[];
  errors: Record<string, string>;
};

function metric(value?: number | null, suffix = "") {
  return value === undefined || value === null ? "—" : `${value}${suffix}`;
}

export function NetworkOperationsCenter({ token }: { token: string }) {
  const [data, setData] = useState<PollingOverview | null>(null);
  const [tab, setTab] = useState<NetworkTab>("devices");
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceId | "">("");
  const [statusFilter, setStatusFilter] = useState("");
  const [siteFilter, setSiteFilter] = useState("");
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  const load = async (force = false): Promise<number> => {
    if (inFlight.current) return data?.poll_interval_seconds || 15;
    inFlight.current = true;
    setWorking(true);
    setError("");

    try {
      const response = await request<unknown>(
        `/network-center/polling${force ? "?force=true" : ""}`,
        token,
      );
      const next = normalizePollingOverview(response);
      setData(next);
      return Math.max(5, next.poll_interval_seconds || 15);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load coordinated network polling",
      );
      return data?.poll_interval_seconds || 15;
    } finally {
      inFlight.current = false;
      setWorking(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    let timer = 0;

    const cycle = async () => {
      let interval = 15;
      if (!document.hidden) interval = await load(false);
      if (!cancelled) {
        timer = window.setTimeout(cycle, interval * 1000);
      }
    };

    const visibilityChanged = () => {
      if (!document.hidden && !inFlight.current) void load(false);
    };

    void cycle();
    document.addEventListener("visibilitychange", visibilityChanged);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", visibilityChanged);
    };
  }, [token]);

  const devices = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();

    return data.devices.filter((device) => {
      const haystack = [
        device.name,
        device.model,
        device.type,
        device.site_name,
        device.ip,
        device.mac,
        device.firmware,
        device.source_id,
        device.source_label,
        device.client_id,
        device.serial_number,
        device.network_id,
      ].join(" ").toLowerCase();

      return (
        (!needle || haystack.includes(needle))
        && (!sourceFilter || device.source === sourceFilter)
        && (!statusFilter || device.status === statusFilter)
        && (!siteFilter || device.site_name === siteFilter)
      );
    });
  }, [
    data,
    query,
    siteFilter,
    sourceFilter,
    statusFilter,
  ]);

  const alarms = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();

    return data.alarms.filter((alarm) => {
      const haystack = [
        alarm.title,
        alarm.detail,
        alarm.device_name,
        alarm.site_name,
        alarm.type,
        alarm.source_label,
      ].join(" ").toLowerCase();

      return (
        (!needle || haystack.includes(needle))
        && (!sourceFilter || alarm.source === sourceFilter)
      );
    });
  }, [data, query, sourceFilter]);

  return (
    <section className="noc-center coordinated-noc">
      <div className="noc-header">
        <div>
          <p className="eyebrow">NETWORK OPERATIONS · RC1 BUILD 032</p>
          <h2>Unified Device Polling</h2>
          <p>
            UISP NMS device telemetry, MikroTik collector state, and
            rate-limit-safe TAUC gateway snapshots in one coordinated view.
          </p>
        </div>
        <div className="noc-header-actions">
          <span className={working ? "poll-state polling" : "poll-state live"}>
            <i />{working ? "Polling" : "Auto polling"}
          </span>
          <button type="button" onClick={() => void load(true)} disabled={working}>
            {working ? "Refreshing…" : "Force refresh"}
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}
      {!!Object.keys(data?.errors || {}).length && (
        <div className="network-source-warnings">
          {Object.entries(data?.errors || {}).map(([source, detail]) => (
            <span key={source}>
              <strong>{source.toUpperCase()}</strong>{detail}
            </span>
          ))}
        </div>
      )}

      <div className="noc-metrics unified-noc-metrics">
        <article><span>All devices</span><strong>{data?.summary.devices_total ?? 0}</strong><small>Three source inventory</small></article>
        <article><span>Online</span><strong>{data?.summary.devices_online ?? 0}</strong><small>Current or fresh cached state</small></article>
        <article><span>Offline</span><strong>{data?.summary.devices_offline ?? 0}</strong><small>Confirmed unavailable</small></article>
        <article><span>Warning / unknown</span><strong>{(data?.summary.devices_warning ?? 0) + (data?.summary.devices_unknown ?? 0)}</strong><small>Needs current telemetry</small></article>
        <article><span>Active alarms</span><strong>{data?.summary.active_alarms ?? 0}</strong><small>{data?.summary.critical_alarms ?? 0} critical</small></article>
        <article><span>Polling sources</span><strong>{data?.summary.sources_healthy ?? 0}/{data?.summary.sources_total ?? 3}</strong><small>Healthy collectors</small></article>
      </div>

      <div className="poll-source-strip">
        {(data?.sources || []).map((source) => (
          <button
            type="button"
            key={source.id}
            className={sourceFilter === source.id ? "selected" : ""}
            onClick={() => setSourceFilter(
              sourceFilter === source.id ? "" : source.id,
            )}
          >
            <i className={`source-state source-${source.state}`} />
            <span><strong>{source.name}</strong><small>{source.mode}</small></span>
            <b>{source.device_count}</b>
          </button>
        ))}
      </div>

      <div className="noc-controls coordinated-noc-controls">
        <div className="noc-tabs">
          <button className={tab === "devices" ? "active" : ""} onClick={() => setTab("devices")}>Devices</button>
          <button className={tab === "alarms" ? "active" : ""} onClick={() => setTab("alarms")}>Alarm Console</button>
          <button className={tab === "sources" ? "active" : ""} onClick={() => setTab("sources")}>Polling Sources</button>
        </div>

        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search device, source, site, IP, MAC, serial…"
        />

        {tab === "devices" && (
          <>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
              <option value="warning">Warning</option>
              <option value="unknown">Unknown</option>
            </select>

            <select value={siteFilter} onChange={(event) => setSiteFilter(event.target.value)}>
              <option value="">All sites / networks</option>
              {(data?.sites || []).map((site) => (
                <option value={site} key={site}>{site}</option>
              ))}
            </select>
          </>
        )}
      </div>

      {tab === "devices" ? (
        <div className="noc-table-wrap">
          <table className="noc-table unified-device-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>Device</th>
                <th>Site / Network</th>
                <th>Identity</th>
                <th>Last poll</th>
                <th>CPU</th>
                <th>Memory</th>
                <th>Latency</th>
                <th>Loss</th>
                <th>Impact / Clients</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.id}>
                  <td><span className={`source-badge source-badge-${device.source}`}>{device.source_label}</span></td>
                  <td><span className={`noc-status ${device.status}`}>{device.status}</span></td>
                  <td>
                    <strong>{device.name}</strong>
                    <small>{device.model} · {display(device.type)}</small>
                  </td>
                  <td>{device.site_name}</td>
                  <td>
                    <code>{device.ip || device.mac || device.serial_number || device.source_id || "—"}</code>
                    {device.firmware && <small>Firmware {device.firmware}</small>}
                  </td>
                  <td>
                    <span>{pollAge(device.last_polled_at)}</span>
                    <small>{display(device.poll_mode)}</small>
                  </td>
                  <td>{metric(device.cpu, "%")}</td>
                  <td>{metric(device.memory, "%")}</td>
                  <td>{metric(device.latency, " ms")}</td>
                  <td>{metric(device.packet_loss, "%")}</td>
                  <td>{device.customer_count}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {!working && !devices.length && (
            <div className="empty-state">No devices match the selected filters.</div>
          )}
        </div>
      ) : tab === "alarms" ? (
        <div className="noc-alarm-list">
          {alarms.map((alarm, index) => (
            <article className={`noc-alarm ${alarm.severity}`} key={`${alarm.source}-${alarm.device_id}-${alarm.type}-${index}`}>
              <div>
                <div>
                  <span className={`source-badge source-badge-${alarm.source}`}>{alarm.source_label}</span>
                  <strong>{alarm.title}</strong>
                  <span>{alarm.site_name} · {alarm.device_name}</span>
                </div>
                <span className={`alarm-level ${alarm.severity}`}>{alarm.severity}</span>
              </div>
              <p>{alarm.detail}</p>
              <small>{alarm.customers_affected} customers potentially affected</small>
            </article>
          ))}

          {!working && !alarms.length && (
            <div className="empty-state">No active network alarms were derived.</div>
          )}
        </div>
      ) : (
        <div className="poll-source-grid">
          {(data?.sources || []).map((source) => (
            <article key={source.id} className={`poll-source-card poll-source-${source.state}`}>
              <header>
                <div><p className="eyebrow">{source.id.toUpperCase()}</p><h3>{source.name}</h3></div>
                <span><i className={`source-state source-${source.state}`} />{display(source.state)}</span>
              </header>
              <dl>
                <div><dt>Polling mode</dt><dd>{source.mode}</dd></div>
                <div><dt>Devices</dt><dd>{source.device_count}</dd></div>
                <div><dt>Cadence</dt><dd>{metric(source.poll_interval_seconds, " sec")}</dd></div>
                <div><dt>Last update</dt><dd>{pollAge(source.last_polled_at)}</dd></div>
                {source.cache_age_seconds !== undefined && source.cache_age_seconds !== null && <div><dt>Cache age</dt><dd>{metric(Math.round(source.cache_age_seconds), " sec")}</dd></div>}
                {source.cached_devices !== undefined && <div><dt>Fresh snapshots</dt><dd>{source.cached_devices}</dd></div>}
              </dl>
              <p>{source.detail}</p>
              {source.id === "tauc" && (
                <small>
                  TAUC device snapshots continue through the existing serialized
                  request queue. This dashboard adds no provider transactions.
                </small>
              )}
            </article>
          ))}
        </div>
      )}

      <footer className="network-poll-footer">
        <span>Dashboard cadence: {data?.poll_interval_seconds ?? 15} seconds</span>
        <span>Mode: {display(data?.mode || "coordinated multi source cache")}</span>
        <span>Updated {pollAge(data?.generated_at)}</span>
      </footer>
    </section>
  );
}

function normalizePollingOverview(value: unknown): PollingOverview {
  if (!isRecord(value)) {
    throw new Error("Network polling returned an invalid response.");
  }

  const summary = isRecord(value.summary) ? value.summary : {};
  const errors = isRecord(value.errors)
    ? Object.fromEntries(
      Object.entries(value.errors).map(([source, detail]) => [
        source,
        String(detail || "Polling source unavailable"),
      ]),
    )
    : {};

  return {
    generated_at: textValue(
      value.generated_at,
      new Date().toISOString(),
    ),
    poll_interval_seconds: numberValue(
      value.poll_interval_seconds,
      15,
    ),
    mode: textValue(value.mode, "coordinated-multi-source-cache"),
    summary: {
      devices_total: numberValue(summary.devices_total),
      devices_online: numberValue(summary.devices_online),
      devices_offline: numberValue(summary.devices_offline),
      devices_warning: numberValue(summary.devices_warning),
      devices_unknown: numberValue(summary.devices_unknown),
      sites_total: numberValue(summary.sites_total),
      active_alarms: numberValue(summary.active_alarms),
      critical_alarms: numberValue(summary.critical_alarms),
      customers_affected: numberValue(summary.customers_affected),
      sources_healthy: numberValue(summary.sources_healthy),
      sources_total: numberValue(summary.sources_total, 3),
    },
    sources: Array.isArray(value.sources)
      ? value.sources.filter(isRecord).map(normalizeSource)
      : [],
    devices: Array.isArray(value.devices)
      ? value.devices.filter(isRecord).map(normalizeDevice)
      : [],
    alarms: Array.isArray(value.alarms)
      ? value.alarms.filter(isRecord).map(normalizeAlarm)
      : [],
    sites: Array.isArray(value.sites)
      ? value.sites.map((site) => String(site || "")).filter(Boolean)
      : [],
    errors,
  };
}

function normalizeSource(source: Record<string, unknown>): PollSource {
  return {
    id: sourceId(source.id),
    name: textValue(source.name, "Polling source"),
    state: sourceState(source.state),
    mode: textValue(source.mode, "Cached polling"),
    device_count: numberValue(source.device_count),
    poll_interval_seconds: optionalNumber(source.poll_interval_seconds),
    last_polled_at: optionalText(source.last_polled_at),
    cache_age_seconds: optionalNumber(source.cache_age_seconds),
    cached_devices: optionalNumber(source.cached_devices) ?? undefined,
    detail: textValue(source.detail, "Polling status unavailable."),
  };
}

function normalizeDevice(device: Record<string, unknown>): Device {
  return {
    ...device,
    id: textValue(device.id, "unknown-device"),
    source_id: textValue(device.source_id),
    source: sourceId(device.source),
    source_label: textValue(device.source_label, "Network"),
    name: textValue(device.name, "Unknown device"),
    model: textValue(device.model, "Unknown"),
    type: textValue(device.type, "network"),
    status: deviceState(device.status),
    site_name: textValue(device.site_name, "Unknown site"),
    ip: optionalText(device.ip),
    mac: optionalText(device.mac),
    firmware: optionalText(device.firmware),
    cpu: optionalNumber(device.cpu),
    memory: optionalNumber(device.memory),
    temperature: optionalNumber(device.temperature),
    signal: optionalNumber(device.signal),
    latency: optionalNumber(device.latency),
    packet_loss: optionalNumber(device.packet_loss),
    customer_count: numberValue(device.customer_count),
    interface_count: optionalNumber(device.interface_count) ?? undefined,
    client_id: optionalText(device.client_id) ?? undefined,
    serial_number: optionalText(device.serial_number) ?? undefined,
    network_id: optionalText(device.network_id) ?? undefined,
    wifi_networks: optionalNumber(device.wifi_networks) ?? undefined,
    warning_count: optionalNumber(device.warning_count) ?? undefined,
    poll_detail: optionalText(device.poll_detail) ?? undefined,
    poll_mode: textValue(device.poll_mode, "cached"),
    poll_interval_seconds: optionalNumber(device.poll_interval_seconds),
    last_polled_at: optionalText(device.last_polled_at),
    cache_age_seconds: optionalNumber(device.cache_age_seconds),
    cache_remaining_seconds: optionalNumber(
      device.cache_remaining_seconds,
    ),
  } as Device;
}

function normalizeAlarm(alarm: Record<string, unknown>): Alarm {
  return {
    severity: alarm.severity === "critical" ? "critical" : "warning",
    type: textValue(alarm.type, "network_warning"),
    title: textValue(alarm.title, "Network warning"),
    detail: textValue(alarm.detail, "No additional detail."),
    device_id: textValue(alarm.device_id),
    device_name: textValue(alarm.device_name, "Unknown device"),
    site_name: textValue(alarm.site_name, "Unknown site"),
    customers_affected: numberValue(alarm.customers_affected),
    source: sourceId(alarm.source),
    source_label: textValue(alarm.source_label, "Network"),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function textValue(value: unknown, fallback = "") {
  if (value === null || value === undefined || value === "") return fallback;
  return typeof value === "string" ? value : String(value);
}

function optionalText(value: unknown) {
  const text = textValue(value);
  return text || null;
}

function numberValue(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function optionalNumber(value: unknown) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function sourceId(value: unknown): SourceId {
  return value === "mikrotik" || value === "tauc" ? value : "uisp";
}

function sourceState(value: unknown): PollSource["state"] {
  if (
    value === "online"
    || value === "degraded"
    || value === "offline"
    || value === "unconfigured"
  ) return value;
  return "degraded";
}

function deviceState(value: unknown): Device["status"] {
  if (
    value === "online"
    || value === "offline"
    || value === "warning"
  ) return value;
  return "unknown";
}

function display(value: unknown) {
  return String(value || "unknown")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function pollAge(value?: string | null) {
  if (!value) return "Waiting for telemetry";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return "Time unavailable";
  const seconds = Math.max(0, Math.round((Date.now() - time) / 1000));
  if (seconds < 5) return "Just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}
