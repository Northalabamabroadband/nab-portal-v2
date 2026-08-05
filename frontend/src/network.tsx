import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type Device = {
  id: string;
  name: string;
  model: string;
  type: string;
  status: string;
  site_name: string;
  ip?: string;
  firmware?: string;
  cpu?: number;
  memory?: number;
  temperature?: number;
  signal?: number;
  latency?: number;
  packet_loss?: number;
  customer_count: number;
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
};

type Overview = {
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
  };
  devices: Device[];
  alarms: Alarm[];
  sites: string[];
};


function metric(value?: number | null, suffix = "") {
  return value === undefined || value === null ? "—" : `${value}${suffix}`;
}

export function NetworkOperationsCenter({ token }: { token: string }) {
  const [data, setData] = useState<Overview | null>(null);
  const [tab, setTab] = useState<"devices" | "alarms">("devices");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [siteFilter, setSiteFilter] = useState("");
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setWorking(true);
    setError("");

    try {
      setData(await request<Overview>("/network-center/overview", token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load network operations");
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60000);
    return () => window.clearInterval(timer);
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
        device.firmware,
        device.id
      ].join(" ").toLowerCase();

      return (
        (!needle || haystack.includes(needle)) &&
        (!statusFilter || device.status === statusFilter) &&
        (!siteFilter || device.site_name === siteFilter)
      );
    });
  }, [data, query, siteFilter, statusFilter]);

  const alarms = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();

    return data.alarms.filter((alarm) => {
      const haystack = [
        alarm.title,
        alarm.detail,
        alarm.device_name,
        alarm.site_name,
        alarm.type
      ].join(" ").toLowerCase();

      return !needle || haystack.includes(needle);
    });
  }, [data, query]);

  return (
    <section className="noc-center">
      <div className="noc-header">
        <div>
          <p className="eyebrow">NETWORK OPERATIONS CENTER</p>
          <h2>Live Network Overview</h2>
          <p>UISP device state, derived alarms, site health, and customer impact.</p>
        </div>
        <button onClick={load}>{working ? "Refreshing…" : "Refresh network"}</button>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="noc-metrics">
        <article><span>Devices</span><strong>{data?.summary.devices_total ?? 0}</strong></article>
        <article><span>Online</span><strong>{data?.summary.devices_online ?? 0}</strong></article>
        <article><span>Offline</span><strong>{data?.summary.devices_offline ?? 0}</strong></article>
        <article><span>Sites</span><strong>{data?.summary.sites_total ?? 0}</strong></article>
        <article><span>Active alarms</span><strong>{data?.summary.active_alarms ?? 0}</strong></article>
        <article><span>Customers affected</span><strong>{data?.summary.customers_affected ?? 0}</strong></article>
      </div>

      <div className="noc-controls">
        <div className="noc-tabs">
          <button className={tab === "devices" ? "active" : ""} onClick={() => setTab("devices")}>Devices</button>
          <button className={tab === "alarms" ? "active" : ""} onClick={() => setTab("alarms")}>Alarm Console</button>
        </div>

        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search device, site, IP, model, alarm…"
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
              <option value="">All sites</option>
              {(data?.sites || []).map((site) => (
                <option value={site} key={site}>{site}</option>
              ))}
            </select>
          </>
        )}
      </div>

      {tab === "devices" ? (
        <div className="noc-table-wrap">
          <table className="noc-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Device</th>
                <th>Site</th>
                <th>IP</th>
                <th>CPU</th>
                <th>Memory</th>
                <th>Temperature</th>
                <th>Latency</th>
                <th>Loss</th>
                <th>Customers</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.id}>
                  <td><span className={`noc-status ${device.status}`}>{device.status}</span></td>
                  <td><strong>{device.name}</strong><small>{device.model} · {device.type}</small></td>
                  <td>{device.site_name}</td>
                  <td><code>{device.ip || "—"}</code></td>
                  <td>{metric(device.cpu, "%")}</td>
                  <td>{metric(device.memory, "%")}</td>
                  <td>{metric(device.temperature, "°")}</td>
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
      ) : (
        <div className="noc-alarm-list">
          {alarms.map((alarm, index) => (
            <article className={`noc-alarm ${alarm.severity}`} key={`${alarm.device_id}-${alarm.type}-${index}`}>
              <div>
                <div>
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
      )}
    </section>
  );
}
