import React, { useEffect, useState } from "react";
import { request as load } from "./api";
import { AccessControl } from "./accessControl";
import { FeatureErrorBoundary } from "./featureErrorBoundary";

type Mode = "parity" | "outages" | "field" | "reports" | "portal" | "admin";
type Json = Record<string, any>;

const endpoint: Record<Mode, string> = {
  parity: "/platform/parity",
  outages: "/platform/outages",
  field: "/platform/field/my-work",
  reports: "/platform/reports/operations",
  portal: "/platform/portal/readiness",
  admin: "/platform/admin/capabilities"
};

const title: Record<Mode, string> = {
  parity: "Capability Parity",
  outages: "Outage Intelligence",
  field: "Ground Crew Mobile Queue",
  reports: "Mission Reporting",
  portal: "Customer Portal",
  admin: "Roles, Permissions & Features"
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
      <div><p className="eyebrow">RC1 BUILD 031</p><h2>{title[mode]}</h2></div>
      <button onClick={refresh}>{working ? "Refreshing…" : "Refresh"}</button>
    </header>
    {error && <div className="error-message">{error}</div>}
    {data && mode === "parity" && <>
      <div className="feature-metrics">
        <Value label="Capability domains" value={data.total_domains} />
        <Value label="Interactive domains" value={data.interactive_domains} />
        <Value label="Release" value={data.release} />
      </div>
      <article className="feature-detail"><h3>Verification basis</h3><p>{data.basis}</p></article>
      <div className="parity-table">
        <div className="parity-row parity-heading"><strong>Domain</strong><strong>Read</strong><strong>Write</strong><strong>Source</strong></div>
        {(data.capabilities || []).map((row: Json) => <div className="parity-row" key={row.domain}><strong>{row.domain}</strong><span>{String(row.read)}</span><span>{String(row.write)}</span><small>{row.source}</small></div>)}
      </div>
      <article className="feature-detail"><h3>Externally controlled operations</h3><ul>{(data.external_controls || []).map((row: string) => <li key={row}>{row}</li>)}</ul></article>
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
    {data && mode === "field" && <>
      <div className="feature-metrics"><Value label="Assigned work" value={data.count} /><Value label="Technician" value={data.technician} /></div>
      <div className="feature-grid">{(data.items || []).map((item: Json) => <article key={item.id}><b>{item.priority}</b><h3>{item.title}</h3><p>{item.service_address || "No address"}</p><strong>{item.status}</strong></article>)}</div>
    </>}
    {data && mode === "reports" && <>
      <div className="feature-metrics"><Value label="Open tickets" value={data.open_tickets} /><Value label="Active work orders" value={data.active_workorders} /><Value label="Low stock" value={data.low_stock_items} /></div>
      <div className="feature-grid"><article><h3>Tickets by status</h3><pre>{JSON.stringify(data.tickets_by_status, null, 2)}</pre></article><article><h3>Work orders by status</h3><pre>{JSON.stringify(data.workorders_by_status, null, 2)}</pre></article></div>
    </>}
    {data && mode === "portal" && <article className="feature-detail"><h3>{data.enabled ? "Enabled" : "Secure activation required"}</h3><p>Customer-facing access remains disabled until identity verification and recovery controls are configured.</p><ul>{(data.requirements || []).map((x: string) => <li key={x}>{x}</li>)}</ul></article>}
    {data && mode === "admin" && <>
      <div className="feature-metrics">
        <Value label="Release" value={data.release} />
        <Value label="Roles" value={Object.keys(data.roles || {}).length} />
        <Value label="Permissions" value={Object.keys(data.permissions || {}).length} />
        <Value label="Administrators" value={data.access?.users?.length ?? 0} />
      </div>
      <FeatureErrorBoundary onRetry={refresh} resetKey={`${mode}:${working}:${error}`}>
        <AccessControl token={token} access={data.access} onChanged={refresh} />
      </FeatureErrorBoundary>
    </>}
  </section>;
}
