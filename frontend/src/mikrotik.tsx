import React, {
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";
import { request } from "./api";

type RouterStatus = {
  key: string;
  name: string;
  site: string;
  role: string;
  enabled: boolean;
  configured: boolean;
  connected: boolean;
  base_url?: string | null;
  identity?: string;
  detail?: string;
  tls_verification: boolean;
  ca_certificate_configured: boolean;
  poll_interval_seconds: number;
  last_attempt_at?: string | null;
  last_seen?: string | null;
  interface_count?: number | null;
};

type FleetResponse = {
  generated_at: string;
  collector: {
    enabled: boolean;
    running: boolean;
    leader: boolean;
    detail: string;
  };
  routers: RouterStatus[];
};

type RouterSnapshot = {
  generated_at: string;
  status: "ready" | "partial";
  mode: string;
  identity: Record<string, unknown>;
  resource: Record<string, unknown>;
  summary: {
    router_name?: string | null;
    platform?: string | null;
    board_name?: string | null;
    version?: string | null;
    uptime?: string | null;
    cpu_load_percent?: number | null;
    memory_used_percent?: number | null;
    interfaces: number;
    interfaces_running: number;
    dhcp_leases: number;
    dhcp_bound: number;
    observed_hosts: number;
    routes: number;
  };
  interfaces: Record<string, unknown>[];
  addresses: Record<string, unknown>[];
  routes: Record<string, unknown>[];
  dhcp_leases: Record<string, unknown>[];
  arp: Record<string, unknown>[];
  network_neighbors: Record<string, unknown>[];
  warnings: string[];
};

type ThroughputHistoryResponse = {
  generated_at: string;
  router_key: string;
  poll_interval_seconds: number;
  mode: string;
  samples: CollectorSample[];
  rollups: unknown[];
};

type InterfaceRate = {
  rx: number;
  tx: number;
};

type RatePoint = {
  timestamp: number;
  rates: Record<string, InterfaceRate>;
};

type CollectorSample = {
  timestamp: string;
  timestamp_ms: number;
  rates: Record<string, InterfaceRate>;
};

const MAX_THROUGHPUT_POINTS = 120;
const MAX_SELECTED_INTERFACES = 6;
const CHART_COLORS = [
  "#38bdf8",
  "#34d399",
  "#fbbf24",
  "#f472b6",
  "#a78bfa",
  "#fb7185"
];

function textValue(value: unknown, fallback = "—"): string {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function routerBoolean(value: unknown): boolean {
  return String(value || "").toLowerCase() === "true";
}

function formatBytes(value: unknown): string {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return textValue(value);
  if (bytes < 1024) return bytes + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let scaled = bytes;
  let unit = -1;
  do {
    scaled /= 1024;
    unit += 1;
  } while (scaled >= 1024 && unit < units.length - 1);
  return scaled.toFixed(scaled >= 10 ? 1 : 2) + " " + units[unit];
}

function formatBitsPerSecond(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 bps";
  const units = ["bps", "Kbps", "Mbps", "Gbps", "Tbps"];
  let scaled = value;
  let unit = 0;
  while (scaled >= 1000 && unit < units.length - 1) {
    scaled /= 1000;
    unit += 1;
  }
  return (
    scaled.toFixed(scaled >= 100 ? 0 : scaled >= 10 ? 1 : 2) +
    " " +
    units[unit]
  );
}

function Stat({
  label,
  value,
  detail
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function ThroughputChart({
  title,
  direction,
  history,
  selectedInterfaces
}: {
  title: string;
  direction: "rx" | "tx";
  history: RatePoint[];
  selectedInterfaces: string[];
}) {
  const width = 720;
  const height = 260;
  const left = 68;
  const right = 16;
  const top = 16;
  const bottom = 34;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const latest = history.length ? history[history.length - 1] : null;

  const ceiling = useMemo(() => {
    const peak = Math.max(
      1,
      ...history.flatMap(point =>
        selectedInterfaces.map(name => point.rates[name]?.[direction] || 0)
      )
    );
    const magnitude = 10 ** Math.floor(Math.log10(peak));
    return Math.max(1, Math.ceil(peak / magnitude) * magnitude);
  }, [direction, history, selectedInterfaces]);

  const xFor = (index: number) => (
    left +
    (history.length <= 1 ? 0 : index / (history.length - 1)) * plotWidth
  );
  const yFor = (value: number) => (
    top + plotHeight - Math.min(1, Math.max(0, value / ceiling)) * plotHeight
  );

  return (
    <article className="throughput-chart">
      <header>
        <div>
          <p className="eyebrow">{direction === "rx" ? "DOWNLOAD / RX" : "UPLOAD / TX"}</p>
          <h4>{title}</h4>
        </div>
        <strong>
          {formatBitsPerSecond(
            selectedInterfaces.reduce(
              (total, name) => total + (latest?.rates[name]?.[direction] || 0),
              0
            )
          )}
        </strong>
      </header>

      <div className="throughput-chart-frame">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${title} for selected MikroTik interfaces`}
          preserveAspectRatio="xMidYMid meet"
        >
          {[0, 0.25, 0.5, 0.75, 1].map(fraction => {
            const y = top + plotHeight - fraction * plotHeight;
            return (
              <g key={fraction}>
                <line
                  className="throughput-grid-line"
                  x1={left}
                  x2={width - right}
                  y1={y}
                  y2={y}
                />
                <text className="throughput-axis-label" x={left - 8} y={y + 4}>
                  {formatBitsPerSecond(ceiling * fraction)}
                </text>
              </g>
            );
          })}

          {selectedInterfaces.map((name, interfaceIndex) => {
            const points = history
              .map((point, pointIndex) => (
                `${xFor(pointIndex)},${yFor(point.rates[name]?.[direction] || 0)}`
              ))
              .join(" ");
            return (
              <polyline
                key={name}
                className="throughput-series"
                points={points}
                stroke={CHART_COLORS[interfaceIndex % CHART_COLORS.length]}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}

          {history.length > 0 && (
            <>
              <text className="throughput-time-label" x={left} y={height - 8}>
                {new Date(history[0].timestamp).toLocaleTimeString()}
              </text>
              <text
                className="throughput-time-label end"
                x={width - right}
                y={height - 8}
              >
                {new Date(history[history.length - 1].timestamp).toLocaleTimeString()}
              </text>
            </>
          )}
        </svg>

        {history.length < 2 && (
          <div className="throughput-chart-waiting">
            Waiting for two live samples…
          </div>
        )}
      </div>

      <div className="throughput-legend">
        {selectedInterfaces.map((name, index) => (
          <span key={name}>
            <i style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />
            {name}
            <strong>
              {formatBitsPerSecond(latest?.rates[name]?.[direction] || 0)}
            </strong>
          </span>
        ))}
      </div>
    </article>
  );
}

export function MikroTikOperations({ token }: { token: string }) {
  const [fleet, setFleet] = useState<FleetResponse | null>(null);
  const [selectedRouterKey, setSelectedRouterKey] = useState("");
  const [status, setStatus] = useState<RouterStatus | null>(null);
  const [snapshot, setSnapshot] = useState<RouterSnapshot | null>(null);
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");
  const [selectedInterfaces, setSelectedInterfaces] = useState<string[]>([]);
  const [throughputHistory, setThroughputHistory] = useState<RatePoint[]>([]);
  const [throughputError, setThroughputError] = useState("");
  const [streamConnected, setStreamConnected] = useState(false);
  const [throughputUpdatedAt, setThroughputUpdatedAt] = useState<number | null>(null);

  const loadFleet = useCallback(async () => {
    try {
      const nextFleet = await request<FleetResponse>("/mikrotik/fleet", token);
      setFleet(nextFleet);
      setSelectedRouterKey(current => {
        if (nextFleet.routers.some(router => router.key === current)) return current;
        return (
          nextFleet.routers.find(router => router.connected)?.key ||
          nextFleet.routers.find(router => router.configured)?.key ||
          nextFleet.routers[0]?.key ||
          ""
        );
      });
      if (!nextFleet.routers.length) setWorking(false);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load the MikroTik fleet"
      );
      setWorking(false);
    }
  }, [token]);

  const loadSnapshot = useCallback(async (routerKey: string) => {
    if (!routerKey) return;
    setWorking(true);
    setError("");
    try {
      setSnapshot(await request<RouterSnapshot>(
        `/mikrotik/routers/${encodeURIComponent(routerKey)}/snapshot`,
        token
      ));
    } catch (caught) {
      setSnapshot(null);
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load MikroTik RouterOS inventory"
      );
    } finally {
      setWorking(false);
    }
  }, [token]);

  useEffect(() => {
    void loadFleet();
    const interval = window.setInterval(() => void loadFleet(), 15000);
    return () => window.clearInterval(interval);
  }, [loadFleet]);

  useEffect(() => {
    const selected = fleet?.routers.find(router => router.key === selectedRouterKey);
    setStatus(selected || null);
  }, [fleet, selectedRouterKey]);

  useEffect(() => {
    setSnapshot(null);
    if (selectedRouterKey) void loadSnapshot(selectedRouterKey);
  }, [loadSnapshot, selectedRouterKey]);

  useEffect(() => {
    if (!snapshot) {
      setSelectedInterfaces([]);
      return;
    }
    const available = snapshot.interfaces
      .map(row => textValue(row.name, ""))
      .filter(Boolean);
    setSelectedInterfaces(current => {
      const valid = current.filter(name => available.includes(name));
      if (valid.length) return valid.slice(0, MAX_SELECTED_INTERFACES);
      const preferred = snapshot.interfaces
        .filter(row => routerBoolean(row.running) && !routerBoolean(row.disabled))
        .map(row => textValue(row.name, ""))
        .filter(Boolean);
      return (preferred.length ? preferred : available).slice(0, 1);
    });
  }, [snapshot]);

  useEffect(() => {
    setThroughputHistory([]);
    setThroughputError("");
    setThroughputUpdatedAt(null);
    setStreamConnected(false);
    if (!selectedRouterKey) return;

    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const appendSample = (sample: CollectorSample) => {
      const timestamp = Number(sample.timestamp_ms) || Date.parse(sample.timestamp);
      if (!Number.isFinite(timestamp)) return;
      setThroughputHistory(current => {
        const next = current.filter(point => point.timestamp !== timestamp);
        next.push({ timestamp, rates: sample.rates || {} });
        next.sort((left, right) => left.timestamp - right.timestamp);
        return next.slice(-MAX_THROUGHPUT_POINTS);
      });
      setThroughputUpdatedAt(timestamp);
    };

    void request<ThroughputHistoryResponse>(
      `/mikrotik/routers/${encodeURIComponent(selectedRouterKey)}/history`,
      token
    ).then(history => {
      if (stopped) return;
      setThroughputHistory(history.samples.map(sample => ({
        timestamp: Number(sample.timestamp_ms) || Date.parse(sample.timestamp),
        rates: sample.rates || {}
      })).filter(point => Number.isFinite(point.timestamp)).slice(-MAX_THROUGHPUT_POINTS));
      const latest = history.samples[history.samples.length - 1];
      if (latest) {
        setThroughputUpdatedAt(
          Number(latest.timestamp_ms) || Date.parse(latest.timestamp)
        );
      }
    }).catch(caught => {
      if (!stopped) {
        setThroughputError(
          caught instanceof Error ? caught.message : "Collector history unavailable"
        );
      }
    });

    const connect = () => {
      if (stopped) return;
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(
        `${scheme}://${window.location.host}/api/v2/live/ws`
      );
      socket.onopen = () => {
        setStreamConnected(true);
        setThroughputError("");
        socket?.send("subscribe");
      };
      socket.onmessage = event => {
        try {
          const payload = JSON.parse(event.data);
          if (
            payload.type === "mikrotik.throughput" &&
            payload.router_key === selectedRouterKey &&
            payload.sample
          ) {
            appendSample(payload.sample as CollectorSample);
          }
        } catch {
          // Ignore non-JSON live messages.
        }
      };
      socket.onerror = () => {
        setThroughputError("Live collector stream is reconnecting");
      };
      socket.onclose = () => {
        setStreamConnected(false);
        if (!stopped) reconnectTimer = window.setTimeout(connect, 2000);
      };
    };
    connect();

    return () => {
      stopped = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [selectedRouterKey, token]);

  const refresh = async () => {
    await loadFleet();
    if (selectedRouterKey) await loadSnapshot(selectedRouterKey);
  };

  const toggleInterface = (name: string) => {
    setSelectedInterfaces(current => {
      if (current.includes(name)) {
        return current.filter(value => value !== name);
      }
      if (current.length >= MAX_SELECTED_INTERFACES) return current;
      return [...current, name];
    });
  };

  return (
    <section className="mikrotik-center">
      <header className="mikrotik-header">
        <div>
          <p className="eyebrow">NETWORK INFRASTRUCTURE · NOC ONLY · RC1 BUILD 027</p>
          <h2>MikroTik RouterOS Fleet</h2>
          <p>
            Centralized telemetry for core, tower, POP, and backhaul-edge routers.
            One backend collector polls each router and distributes the same live
            samples to every NOC operator.
          </p>
        </div>
        <div className="mikrotik-header-actions">
          <span className={
            "router-state " +
            (status?.connected ? "connected" : status?.configured ? "failed" : "missing")
          }>
            {status?.connected
              ? "Connected"
              : status?.configured
                ? "Connection failed"
                : "Configuration required"}
          </span>
          <button onClick={() => void refresh()} disabled={working}>
            {working ? "Refreshing RouterOS…" : "Refresh selected router"}
          </button>
        </div>
      </header>

      {error && <div className="error-message">{error}</div>}

      {fleet && (
        <section className="mikrotik-fleet">
          <div className="mikrotik-panel-heading">
            <div>
              <p className="eyebrow">ROUTER FLEET</p>
              <h3>Infrastructure sites</h3>
              <p>
                {fleet.collector.detail}
              </p>
            </div>
            <span className={
              fleet.collector.running
                ? "throughput-live"
                : "throughput-live failed"
            }>
              <i />
              {fleet.collector.leader
                ? "Collector leader"
                : fleet.collector.running
                  ? "Collector standby"
                  : "Collector stopped"}
            </span>
          </div>
          <div className="mikrotik-fleet-grid">
            {fleet.routers.map(router => (
              <button
                key={router.key}
                className={
                  "mikrotik-router-card " +
                  (router.key === selectedRouterKey ? "selected " : "") +
                  (router.connected ? "online" : "")
                }
                onClick={() => setSelectedRouterKey(router.key)}
              >
                <span className={
                  "neighbor-beacon " + (router.connected ? "online" : "offline")
                } />
                <span>
                  <strong>{router.name}</strong>
                  <small>
                    {[router.site, router.role].filter(Boolean).join(" · ") ||
                      router.key}
                  </small>
                </span>
                <em>{router.connected ? "Live" : router.enabled ? "Offline" : "Disabled"}</em>
              </button>
            ))}
            {!fleet.routers.length && (
              <p className="muted">No MikroTik router profiles are configured.</p>
            )}
          </div>
        </section>
      )}

      {fleet && !fleet.routers.length && (
        <article className="mikrotik-setup">
          <p className="eyebrow">SECURE FLEET ACTIVATION</p>
          <h3>Add the mounted MikroTik routers secret</h3>
          <p>
            Create <code>secrets/mikrotik/routers.json</code> on the server. The
            file is mounted read-only into the API container and must never be
            committed.
          </p>
        </article>
      )}

      {status && !status.configured && (
        <article className="mikrotik-setup">
          <p className="eyebrow">SECURE ACTIVATION</p>
          <h3>Connect {status.name} to RouterOS v7</h3>
          <p>
            Add this router to the server&apos;s private routers file, or keep using
            the legacy single-router environment variables. Use a dedicated
            read-only REST account.
          </p>
          <code>
            MIKROTIK_ROUTERS_FILE=/run/secrets/mikrotik/routers.json
          </code>
          <small>
            TLS verification is enabled by default. Credentials are never returned
            by the API or rendered in this page.
          </small>
        </article>
      )}

      {status?.configured && !status.connected && (
        <article className="mikrotik-setup failed">
          <p className="eyebrow">ROUTEROS PROBE FAILED</p>
          <h3>{status.detail || "The router did not accept the health probe."}</h3>
          <p>
            Verify routing and firewall access from the API container, the www-ssl
            service, the certificate trust chain, and the account policies.
          </p>
        </article>
      )}

      {snapshot && (
        <>
          <div className="mikrotik-metrics">
            <Stat
              label="Router identity"
              value={textValue(snapshot.summary.router_name, "RouterOS")}
              detail={[
                snapshot.summary.board_name,
                snapshot.summary.platform
              ].filter(Boolean).join(" · ") || "Board identity unavailable"}
            />
            <Stat
              label="RouterOS"
              value={textValue(snapshot.summary.version)}
              detail={"Uptime " + textValue(snapshot.summary.uptime)}
            />
            <Stat
              label="CPU load"
              value={
                snapshot.summary.cpu_load_percent == null
                  ? "—"
                  : snapshot.summary.cpu_load_percent + "%"
              }
              detail={textValue(snapshot.resource["cpu"], "Processor telemetry")}
            />
            <Stat
              label="Memory used"
              value={
                snapshot.summary.memory_used_percent == null
                  ? "—"
                  : snapshot.summary.memory_used_percent + "%"
              }
              detail={formatBytes(snapshot.resource["free-memory"]) + " free"}
            />
            <Stat
              label="Interfaces"
              value={
                snapshot.summary.interfaces_running +
                " / " +
                snapshot.summary.interfaces
              }
              detail="Running / total"
            />
            <Stat
              label="Observed hosts"
              value={String(snapshot.summary.observed_hosts)}
              detail={snapshot.summary.dhcp_bound + " bound DHCP leases"}
            />
          </div>

          {!!snapshot.warnings.length && (
            <details className="mikrotik-warnings" open={snapshot.status === "partial"}>
              <summary>
                Partial telemetry · {snapshot.warnings.length} RouterOS resource
                {snapshot.warnings.length === 1 ? "" : "s"} unavailable
              </summary>
              <ul>
                {snapshot.warnings.map(warning => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </details>
          )}

          <article className="mikrotik-panel">
            <div className="mikrotik-panel-heading">
              <div>
                <p className="eyebrow">INTERFACE TELEMETRY</p>
                <h3>Router ports and traffic</h3>
              </div>
              <span>
                {selectedInterfaces.length} selected · {snapshot.interfaces.length} total
              </span>
            </div>
            <p className="throughput-selection-help">
              Select up to {MAX_SELECTED_INTERFACES} ports to graph live throughput.
            </p>
            <div className="router-table-wrap">
              <table className="router-table">
                <thead>
                  <tr>
                    <th>Graph</th>
                    <th>Interface</th>
                    <th>Type</th>
                    <th>State</th>
                    <th>MTU</th>
                    <th>RX</th>
                    <th>TX</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.interfaces.map((row, index) => {
                    const name = textValue(row.name, `Interface ${index + 1}`);
                    const selected = selectedInterfaces.includes(name);
                    return (
                      <tr
                        key={textValue(row[".id"], String(index))}
                        className={selected ? "throughput-selected-row" : ""}
                      >
                        <td>
                          <input
                            type="checkbox"
                            checked={selected}
                            disabled={
                              !selected &&
                              selectedInterfaces.length >= MAX_SELECTED_INTERFACES
                            }
                            aria-label={`Graph ${name}`}
                            onChange={() => toggleInterface(name)}
                          />
                        </td>
                        <td>
                          <strong>{name}</strong>
                          <small>{textValue(row["mac-address"], "")}</small>
                        </td>
                        <td>{textValue(row.type)}</td>
                        <td>
                          <span className={
                            "table-state " +
                            (routerBoolean(row.running) && !routerBoolean(row.disabled)
                              ? "online"
                              : "offline")
                          }>
                            {routerBoolean(row.disabled)
                              ? "Disabled"
                              : routerBoolean(row.running)
                                ? "Running"
                                : "Down"}
                          </span>
                        </td>
                        <td>{textValue(row["actual-mtu"] || row.mtu)}</td>
                        <td>{formatBytes(row["rx-byte"])}</td>
                        <td>{formatBytes(row["tx-byte"])}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </article>

          <div className="mikrotik-split">
            <article className="mikrotik-panel">
              <div className="mikrotik-panel-heading">
                <div>
                  <p className="eyebrow">INFRASTRUCTURE ADJACENCY</p>
                  <h3>Observed network hosts</h3>
                </div>
                <span>{snapshot.network_neighbors.length} observed</span>
              </div>
              <div className="router-neighbor-list">
                {snapshot.network_neighbors.map((row, index) => (
                  <div key={textValue(row.id, String(index))}>
                    <span className={
                      "neighbor-beacon " +
                      (row.active ? "online" : "offline")
                    } />
                    <div>
                      <strong>{textValue(row.hostname, "Unnamed client")}</strong>
                      <small>
                        {textValue(row.ip_address)} · {textValue(row.mac_address)}
                      </small>
                    </div>
                    <div>
                      <span>{textValue(row.interface, "LAN")}</span>
                      <small>{textValue(row.source)}</small>
                    </div>
                  </div>
                ))}
                {!snapshot.network_neighbors.length && (
                  <p className="muted">
                    RouterOS returned no DHCP or ARP network neighbors.
                  </p>
                )}
              </div>
            </article>

            <article className="mikrotik-panel">
              <div className="mikrotik-panel-heading">
                <div>
                  <p className="eyebrow">ROUTING & ADDRESSING</p>
                  <h3>Active network paths</h3>
                </div>
                <span>{snapshot.summary.routes} routes</span>
              </div>
              <div className="router-route-list">
                {snapshot.routes.slice(0, 40).map((row, index) => (
                  <div key={textValue(row[".id"], String(index))}>
                    <strong>{textValue(row["dst-address"], "Dynamic route")}</strong>
                    <span>
                      {textValue(
                        row.gateway || row["immediate-gw"],
                        textValue(row["routing-table"], "main")
                      )}
                    </span>
                    <small>
                      {routerBoolean(row.active) ? "Active" : "Inactive"} · distance{" "}
                      {textValue(row.distance, "—")}
                    </small>
                  </div>
                ))}
                {!snapshot.routes.length && (
                  <p className="muted">RouterOS returned no route records.</p>
                )}
              </div>
            </article>
          </div>

          <section className="mikrotik-throughput">
            <div className="mikrotik-panel-heading">
              <div>
                <p className="eyebrow">LIVE PORT THROUGHPUT</p>
                <h3>Selected interface traffic</h3>
                <p>
                  Server-side sampling · Redis live history · PostgreSQL minute rollups
                </p>
              </div>
              <span className={throughputError ? "throughput-live failed" : "throughput-live"}>
                <i />
                {throughputError
                  ? "Stream issue"
                  : streamConnected
                    ? "Live fan-out"
                    : "Connecting"}
              </span>
            </div>

            {throughputError && (
              <div className="throughput-error">{throughputError}</div>
            )}

            {selectedInterfaces.length ? (
              <div className="throughput-grid">
                <ThroughputChart
                  title="Receive throughput"
                  direction="rx"
                  history={throughputHistory}
                  selectedInterfaces={selectedInterfaces}
                />
                <ThroughputChart
                  title="Transmit throughput"
                  direction="tx"
                  history={throughputHistory}
                  selectedInterfaces={selectedInterfaces}
                />
              </div>
            ) : (
              <div className="throughput-empty">
                Select one or more ports in the interface table to start both graphs.
              </div>
            )}

            <footer>
              <span>{selectedInterfaces.length} / {MAX_SELECTED_INTERFACES} ports</span>
              <span>{throughputHistory.length} / {MAX_THROUGHPUT_POINTS} samples</span>
              <span>
                {throughputUpdatedAt
                  ? `Last sample ${new Date(throughputUpdatedAt).toLocaleTimeString()}`
                  : "Awaiting first sample"}
              </span>
            </footer>
          </section>

          <footer className="mikrotik-footnote">
            <span>Internal NOC only</span>
            <span>Read-only · no customer assignments</span>
            <span>HTTP Basic credentials protected by TLS</span>
            <span>One fleet collector · no per-browser router polling</span>
            <span>
              Last inventory poll {new Date(snapshot.generated_at).toLocaleString()}
            </span>
          </footer>
        </>
      )}
    </section>
  );
}
