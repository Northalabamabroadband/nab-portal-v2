import React, { useEffect, useState } from "react";
import { request } from "./api";

type StatusCounts = Record<string, number>;

type MissionOverview = {
  generated_at: string;
  mission_state: "operational" | "degraded" | "critical";
  summary: {
    active_outages: number;
    customers_affected: number;
    open_tickets: number;
    active_workorders: number;
    unacknowledged_alerts: number;
    critical_alerts: number;
  };
  network: {
    devices_total: number;
    devices_online: number;
    devices_offline: number;
    devices_warning: number;
    devices_unknown: number;
    sites_total: number;
    active_alarms: number;
    critical_alarms: number;
    customers_affected: number;
    error?: string | null;
  };
  operations: {
    tickets_by_status: StatusCounts;
    workorders_by_status: StatusCounts;
    low_stock_items: number;
    unassigned_workorders: number;
  };
  managed_wifi: {
    customers: number;
    gateways: number;
    networks: number;
  };
  recent_activity: Array<{
    id: string;
    kind: "ticket" | "workorder" | "alert";
    title: string;
    detail: string;
    status: string;
    occurred_at: string;
  }>;
};

type LiveSummary = {
  status: string;
  uisp: Record<string, unknown>;
  tauc: Record<string, unknown>;
  mikrotik: Record<string, unknown>;
};

export function MissionControlOverview({
  token,
  liveSummary,
  onNavigate,
}: {
  token: string;
  liveSummary: LiveSummary | null;
  onNavigate: (page: string) => void;
}) {
  const [data, setData] = useState<MissionOverview | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    setWorking(true);
    setError("");
    request<MissionOverview>("/platform/mission-control", token)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((caught) => {
        if (active) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load Mission Control",
          );
        }
      })
      .finally(() => {
        if (active) setWorking(false);
      });
    return () => {
      active = false;
    };
  }, [refreshKey, token]);

  const missionState = data?.mission_state || "degraded";

  return (
    <section className="mission-control">
      <header className={`mission-control-header mission-state-${missionState}`}>
        <div>
          <p className="eyebrow">FLIGHT OPERATIONS · RC1 BUILD 029</p>
          <h2>Mission Control</h2>
          <p>
            One operational view across network health, incidents, workload,
            managed Wi‑Fi, and platform integrations.
          </p>
        </div>
        <div className="mission-control-header-actions">
          <span className={`mission-state-badge mission-state-${missionState}`}>
            <i />
            {label(missionState)}
          </span>
          <button
            type="button"
            onClick={() => setRefreshKey((key) => key + 1)}
            disabled={working}
          >
            {working ? "Refreshing…" : "Refresh overview"}
          </button>
        </div>
      </header>

      {error && <div className="error-message">{error}</div>}
      {data?.network.error && (
        <div className="mission-control-warning">
          <strong>UISP NMS telemetry unavailable.</strong>
          <span>{data.network.error}</span>
          <small>Local operational workload remains available below.</small>
        </div>
      )}

      <div className="mission-control-metrics">
        <MissionMetric
          label="Mission state"
          value={label(missionState)}
          detail={liveSummary?.status || "Portal operational state"}
          tone={missionState}
        />
        <MissionMetric
          label="Active outages"
          value={String(data?.summary.active_outages ?? 0)}
          detail={`${data?.summary.customers_affected ?? 0} customers affected`}
          tone={(data?.summary.active_outages ?? 0) ? "critical" : "operational"}
        />
        <MissionMetric
          label="Open tickets"
          value={String(data?.summary.open_tickets ?? 0)}
          detail="Support workload"
        />
        <MissionMetric
          label="Active work orders"
          value={String(data?.summary.active_workorders ?? 0)}
          detail={`${data?.operations.unassigned_workorders ?? 0} unassigned`}
        />
        <MissionMetric
          label="Unacknowledged alerts"
          value={String(data?.summary.unacknowledged_alerts ?? 0)}
          detail={`${data?.summary.critical_alerts ?? 0} critical`}
          tone={(data?.summary.critical_alerts ?? 0) ? "critical" : "neutral"}
        />
      </div>

      <div className="mission-control-grid">
        <article className="mission-panel network-posture">
          <div className="mission-panel-heading">
            <div>
              <p className="eyebrow">UISP NMS</p>
              <h3>Network posture</h3>
            </div>
            <button type="button" onClick={() => onNavigate("Network")}>
              Open network →
            </button>
          </div>
          <div className="network-posture-ring">
            <div>
              <strong>{data?.network.devices_online ?? 0}</strong>
              <span>online</span>
            </div>
          </div>
          <dl className="mission-stat-list">
            <div><dt>Total devices</dt><dd>{data?.network.devices_total ?? 0}</dd></div>
            <div><dt>Offline</dt><dd className="danger">{data?.network.devices_offline ?? 0}</dd></div>
            <div><dt>Warning</dt><dd className="warning">{data?.network.devices_warning ?? 0}</dd></div>
            <div><dt>Sites reporting</dt><dd>{data?.network.sites_total ?? 0}</dd></div>
            <div><dt>Active alarms</dt><dd>{data?.network.active_alarms ?? 0}</dd></div>
          </dl>
        </article>

        <article className="mission-panel">
          <div className="mission-panel-heading">
            <div>
              <p className="eyebrow">OPERATIONS LOAD</p>
              <h3>Tickets & dispatch</h3>
            </div>
            <button type="button" onClick={() => onNavigate("Operations Suite")}>
              Open suite →
            </button>
          </div>
          <StatusBreakdown
            title="Support tickets"
            counts={data?.operations.tickets_by_status || {}}
          />
          <StatusBreakdown
            title="Work orders"
            counts={data?.operations.workorders_by_status || {}}
          />
          <div className="mission-callouts">
            <span><strong>{data?.operations.unassigned_workorders ?? 0}</strong> unassigned work orders</span>
            <span><strong>{data?.operations.low_stock_items ?? 0}</strong> low-stock items</span>
          </div>
        </article>

        <article className="mission-panel">
          <div className="mission-panel-heading">
            <div>
              <p className="eyebrow">SERVICE PLATFORMS</p>
              <h3>Integration readiness</h3>
            </div>
            <button type="button" onClick={() => onNavigate("Systems Check")}>
              Systems check →
            </button>
          </div>
          <div className="integration-readiness">
            <IntegrationState
              name="UISP"
              ready={Boolean(liveSummary?.uisp?.connected)}
              configured={Boolean(liveSummary?.uisp?.configured)}
            />
            <IntegrationState
              name="TAUC"
              ready={Boolean(liveSummary?.tauc?.connected)}
              configured={Boolean(liveSummary?.tauc?.configured)}
            />
            <IntegrationState
              name="MikroTik Core"
              ready={Boolean(liveSummary?.mikrotik?.connected)}
              configured={Boolean(liveSummary?.mikrotik?.configured)}
            />
            <IntegrationState name="Customer 360" ready configured />
            <IntegrationState name="Mission telemetry" ready={Boolean(data)} configured />
          </div>
        </article>

        <article className="mission-panel managed-wifi-posture">
          <div className="mission-panel-heading">
            <div>
              <p className="eyebrow">MANAGED WI‑FI</p>
              <h3>Customer fleet</h3>
            </div>
            <button type="button" onClick={() => onNavigate("Managed Wi-Fi")}>
              Open Wi‑Fi →
            </button>
          </div>
          <div className="managed-wifi-counts">
            <div><strong>{data?.managed_wifi.customers ?? 0}</strong><span>customers</span></div>
            <div><strong>{data?.managed_wifi.gateways ?? 0}</strong><span>gateways</span></div>
            <div><strong>{data?.managed_wifi.networks ?? 0}</strong><span>networks</span></div>
          </div>
          <button
            className="mission-customer-action"
            type="button"
            onClick={() => onNavigate("Customers")}
          >
            Open customer directory
          </button>
        </article>

        <article className="mission-panel mission-activity">
          <div className="mission-panel-heading">
            <div>
              <p className="eyebrow">RECENT ACTIVITY</p>
              <h3>Operations timeline</h3>
            </div>
            <span>{data?.recent_activity.length ?? 0} events</span>
          </div>
          <div className="mission-activity-list">
            {(data?.recent_activity || []).map((item) => (
              <div className={`mission-activity-item activity-${item.kind}`} key={`${item.kind}-${item.id}`}>
                <i aria-hidden="true" />
                <div>
                  <header>
                    <strong>{item.title}</strong>
                    <time dateTime={item.occurred_at}>{relativeTime(item.occurred_at)}</time>
                  </header>
                  <p>{item.detail}</p>
                  <small>{label(item.kind)} · {label(item.status)}</small>
                </div>
              </div>
            ))}
            {!working && !data?.recent_activity.length && (
              <p className="mission-empty">No recent operational activity.</p>
            )}
          </div>
        </article>
      </div>

      <nav className="mission-quick-actions" aria-label="Mission Control quick actions">
        <button type="button" onClick={() => onNavigate("Incident Command")}>◆ Incident Command</button>
        <button type="button" onClick={() => onNavigate("Customers")}>◉ Customers</button>
        <button type="button" onClick={() => onNavigate("MikroTik NOC")}>⌗ MikroTik NOC</button>
        <button type="button" onClick={() => onNavigate("Flight Alerts")}>⚠ Flight Alerts</button>
      </nav>
    </section>
  );
}

function MissionMetric({
  label: metricLabel,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <article className={`mission-metric metric-${tone}`}>
      <span>{metricLabel}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function StatusBreakdown({
  title,
  counts,
}: {
  title: string;
  counts: StatusCounts;
}) {
  const entries = Object.entries(counts).sort((left, right) => right[1] - left[1]);
  return (
    <div className="status-breakdown">
      <h4>{title}</h4>
      <div>
        {entries.length
          ? entries.map(([status, count]) => (
              <span key={status}><strong>{count}</strong>{label(status)}</span>
            ))
          : <span><strong>0</strong>No records</span>}
      </div>
    </div>
  );
}

function IntegrationState({
  name,
  ready,
  configured,
}: {
  name: string;
  ready: boolean;
  configured: boolean;
}) {
  const state = ready ? "Connected" : configured ? "Unavailable" : "Not configured";
  return (
    <div>
      <span><i className={ready ? "ready" : configured ? "warning" : ""} />{name}</span>
      <strong>{state}</strong>
    </div>
  );
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function relativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  const seconds = Math.round((timestamp - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(seconds) < 60) return formatter.format(seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  return formatter.format(Math.round(hours / 24), "day");
}
