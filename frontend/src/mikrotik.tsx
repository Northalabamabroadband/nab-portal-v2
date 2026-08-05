import React, { useEffect, useState } from "react";
import { request } from "./api";

type RouterStatus = {
  configured: boolean;
  connected: boolean;
  base_url?: string | null;
  identity?: string;
  detail?: string;
  tls_verification: boolean;
  ca_certificate_configured: boolean;
  mode: string;
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

export function MikroTikOperations({ token }: { token: string }) {
  const [status, setStatus] = useState<RouterStatus | null>(null);
  const [snapshot, setSnapshot] = useState<RouterSnapshot | null>(null);
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");

  const refresh = async () => {
    setWorking(true);
    setError("");
    try {
      const nextStatus = await request<RouterStatus>("/mikrotik/status", token);
      setStatus(nextStatus);
      if (nextStatus.configured) {
        setSnapshot(await request<RouterSnapshot>("/mikrotik/snapshot", token));
      } else {
        setSnapshot(null);
      }
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load MikroTik RouterOS"
      );
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [token]);

  return (
    <section className="mikrotik-center">
      <header className="mikrotik-header">
        <div>
          <p className="eyebrow">NETWORK INFRASTRUCTURE · NOC ONLY · RC1 BUILD 025</p>
          <h2>MikroTik RouterOS Infrastructure</h2>
          <p>
            Internal core, tower, POP, and backhaul-edge router health. This
            module is isolated from Customer 360, subscriber Wi-Fi, and customer
            equipment assignments.
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
            {working ? "Polling RouterOS…" : "Refresh telemetry"}
          </button>
        </div>
      </header>

      {error && <div className="error-message">{error}</div>}

      {status && !status.configured && (
        <article className="mikrotik-setup">
          <p className="eyebrow">SECURE ACTIVATION</p>
          <h3>Connect the NOC to a RouterOS v7 infrastructure router</h3>
          <p>
            Add the variables below to the deployed server&apos;s private .env file.
            Use a dedicated infrastructure-monitoring account limited to read and
            REST API access. This does not assign routers to customer records.
          </p>
          <code>
            MIKROTIK_BASE_URL · MIKROTIK_USERNAME · MIKROTIK_PASSWORD
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
              detail={
                formatBytes(snapshot.resource["free-memory"]) + " free"
              }
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
              detail={
                snapshot.summary.dhcp_bound +
                " bound DHCP leases"
              }
            />
          </div>

          {!!snapshot.warnings.length && (
            <details className="mikrotik-warnings" open={snapshot.status === "partial"}>
              <summary>
                Partial telemetry · {snapshot.warnings.length} RouterOS resource
                {snapshot.warnings.length === 1 ? "" : "s"} unavailable
              </summary>
              <ul>
                {snapshot.warnings.map((warning) => (
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
              <span>{snapshot.interfaces.length} interfaces</span>
            </div>
            <div className="router-table-wrap">
              <table className="router-table">
                <thead>
                  <tr>
                    <th>Interface</th>
                    <th>Type</th>
                    <th>State</th>
                    <th>MTU</th>
                    <th>RX</th>
                    <th>TX</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.interfaces.map((row, index) => (
                    <tr key={textValue(row[".id"], String(index))}>
                      <td>
                        <strong>{textValue(row.name, "Unnamed")}</strong>
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
                  ))}
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
              <div className="router-client-list">
                {snapshot.network_neighbors.map((row, index) => (
                  <div key={textValue(row.id, String(index))}>
                    <span className={
                      "client-beacon " +
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

          <footer className="mikrotik-footnote">
            <span>Internal NOC only</span>
            <span>Read-only · no customer assignments</span>
            <span>HTTP Basic credentials protected by TLS</span>
            <span>
              Last poll {new Date(snapshot.generated_at).toLocaleString()}
            </span>
          </footer>
        </>
      )}
    </section>
  );
}
