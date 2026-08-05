import React, { useEffect, useState } from "react";
import { request as load } from "./api";

type Mode = "incidents" | "outages" | "network" | "field" | "reports" | "portal" | "admin" | "wifi";
type Json = Record<string, any>;

const endpoint: Record<Mode, string> = {
  incidents: "/platform/incidents/command",
  outages: "/platform/outages",
  network: "/platform/network-intelligence",
  field: "/platform/field/my-work",
  reports: "/platform/reports/operations",
  portal: "/platform/portal/readiness",
  admin: "/platform/admin/capabilities",
  wifi: "/integrations/health"
};

const title: Record<Mode, string> = {
  incidents: "Incident Command",
  outages: "Outage Intelligence",
  network: "Network Topology & Performance",
  field: "Ground Crew Mobile Queue",
  reports: "Mission Reporting",
  portal: "Customer Portal",
  admin: "Roles, Permissions & Features",
  wifi: "Managed Wi-Fi Flight Controls"
};

function Value({ label, value }: { label: string; value: unknown }) {
  return <article><span>{label}</span><strong>{value == null ? "—" : String(value)}</strong></article>;
}

export function FeatureHub({ token, mode }: { token: string; mode: Mode }) {
  const [data, setData] = useState<Json | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const refresh = async () => {
    setWorking(true); setError("");
    try {
      if (mode === "admin") {
        const [capabilities, access] = await Promise.all([
          load<Json>(endpoint[mode], token),
          load<Json>("/admin/access", token)
        ]);
        setData({ ...capabilities, access });
      } else {
        setData(await load<Json>(endpoint[mode], token));
      }
    }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load feature"); }
    finally { setWorking(false); }
  };

  useEffect(() => { refresh(); }, [mode, token]);

  return <section className="feature-hub">
    <header>
      <div><p className="eyebrow">RC1 BUILD 007</p><h2>{title[mode]}</h2></div>
      <button onClick={refresh}>{working ? "Refreshing…" : "Refresh"}</button>
    </header>
    {error && <div className="error-message">{error}</div>}
    {data && mode === "incidents" && <>
      <div className="incident-state">
        <span>Mission state</span>
        <strong className={`state-${data.mission_state}`}>{String(data.mission_state || "unknown")}</strong>
      </div>
      <div className="feature-metrics">
        <Value label="Active incidents" value={data.summary?.active_incidents} />
        <Value label="Customers affected" value={data.summary?.customers_affected} />
        <Value label="Critical alerts" value={data.summary?.critical_alerts} />
        <Value label="Unassigned ground work" value={data.summary?.unassigned_workorders} />
      </div>
      <div className="feature-grid incident-grid">{(data.incidents || []).map((incident: Json) =>
        <article key={incident.id}>
          <b>{incident.severity}</b>
          <h3>{incident.site_name}</h3>
          <p>{incident.devices.length} device{incident.devices.length === 1 ? "" : "s"} offline · {incident.customers_affected} customers affected</p>
          <strong>{incident.alert_count} linked alerts</strong>
          <small>{incident.recommended_action}</small>
        </article>
      )}</div>
      {!data.incidents?.length && <article className="feature-detail"><h3>All systems nominal</h3><p>No active device-offline incidents were detected in the current UISP telemetry.</p></article>}
    </>}
    {data && mode === "outages" && <>
      <div className="feature-metrics">
        <Value label="Active outages" value={data.active_outages} />
        <Value label="Offline devices" value={data.offline_devices} />
        <Value label="Customers affected" value={data.customers_affected} />
      </div>
      <div className="feature-grid">{(data.events || []).map((event: Json) =>
        <article key={event.site_name}><b>Critical</b><h3>{event.site_name}</h3><p>{event.devices.length} devices offline</p><strong>{event.customers_affected} customers affected</strong></article>
      )}</div>
    </>}
    {data && mode === "network" && <>
      <div className="feature-metrics">
        <Value label="Devices" value={data.summary?.devices_total} />
        <Value label="Sites" value={data.summary?.sites_total} />
        <Value label="Average latency" value={data.performance?.average_latency_ms == null ? "—" : `${data.performance.average_latency_ms} ms`} />
        <Value label="Packet loss" value={data.performance?.average_packet_loss == null ? "—" : `${data.performance.average_packet_loss}%`} />
      </div>
      <div className="feature-grid">{(data.fleet_models || []).map((row: Json) => <article key={row.model}><h3>{row.model}</h3><strong>{row.count} devices</strong></article>)}</div>
    </>}
    {data && mode === "field" && <>
      <div className="feature-metrics"><Value label="Assigned work" value={data.count} /><Value label="Technician" value={data.technician} /></div>
      <div className="feature-grid">{(data.items || []).map((item: Json) => <article key={item.id}><b>{item.priority}</b><h3>{item.title}</h3><p>{item.service_address || "No address"}</p><strong>{item.status}</strong></article>)}</div>
    </>}
    {data && mode === "reports" && <>
      <div className="feature-metrics"><Value label="Open tickets" value={data.open_tickets} /><Value label="Active work orders" value={data.active_workorders} /><Value label="Low stock" value={data.low_stock_items} /></div>
      <div className="feature-grid"><article><h3>Tickets by status</h3><pre>{JSON.stringify(data.tickets_by_status, null, 2)}</pre></article><article><h3>Work orders by status</h3><pre>{JSON.stringify(data.workorders_by_status, null, 2)}</pre></article></div>
    </>}
    {data && mode === "portal" && <article className="feature-detail"><h3>{data.enabled ? "Enabled" : "Secure activation required"}</h3><p>Customer-facing access remains disabled until identity verification and recovery controls are configured.</p><ul>{(data.requirements || []).map((x: string) => <li key={x}>{x}</li>)}</ul></article>}
    {data && mode === "admin" && <><div className="feature-metrics"><Value label="Release" value={data.release} /><Value label="Roles" value={Object.keys(data.roles || {}).length} /><Value label="Permissions" value={Object.keys(data.permissions || {}).length} /><Value label="Administrators" value={data.access?.users?.length ?? 0} /></div><div className="feature-grid">{Object.entries(data.features || {}).map(([name, state]) => <article key={name}><h3>{name.replaceAll("_", " ")}</h3><strong>{String(state)}</strong></article>)}</div></>}
    {data && mode === "wifi" && <div className="feature-grid"><article><h3>TAUC</h3><strong>{data.tauc?.configured ? "Configured" : "Configuration required"}</strong><p>SSID, password, reboot, and diagnostics controls remain permission and endpoint gated.</p></article><article><h3>Customer gateway workflow</h3><p>Open Customer 360 to resolve a gateway and view managed Wi-Fi identity.</p></article></div>}
  </section>;
}
