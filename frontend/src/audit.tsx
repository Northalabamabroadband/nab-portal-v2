import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type AuditEvent = {
  id: string;
  actor_email?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  method: string;
  path: string;
  status_code?: number;
  ip_address?: string;
  detail: string;
  created_at: string;
};


export function AuditCenter({ token }: { token: string }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [query, setQuery] = useState("");
  const [method, setMethod] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(true);

  const load = async () => {
    setWorking(true);
    setError("");

    try {
      setEvents(await request<AuditEvent[]>("/audit?limit=500", token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load audit events");
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    load();
  }, [token]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();

    return events.filter((event) => {
      const matchesMethod = !method || event.method === method;
      const haystack = [
        event.actor_email,
        event.action,
        event.resource_type,
        event.resource_id,
        event.method,
        event.path,
        event.status_code,
        event.ip_address,
        event.detail
      ].join(" ").toLowerCase();

      return matchesMethod && (!needle || haystack.includes(needle));
    });
  }, [events, method, query]);

  return (
    <section className="audit-center">
      <div className="audit-header">
        <div>
          <p className="eyebrow">SECURITY & COMPLIANCE</p>
          <h2>Audit Center</h2>
          <p>Review administrative activity across Portal v2.</p>
        </div>
        <button onClick={load}>{working ? "Refreshing…" : "Refresh"}</button>
      </div>

      <div className="audit-filters">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search actor, action, path, IP, status…"
        />
        <select value={method} onChange={(event) => setMethod(event.target.value)}>
          <option value="">All methods</option>
          <option value="GET">GET</option>
          <option value="POST">POST</option>
          <option value="PATCH">PATCH</option>
          <option value="PUT">PUT</option>
          <option value="DELETE">DELETE</option>
        </select>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="audit-summary">
        <span>{filtered.length} visible events</span>
        <span>{events.length} total loaded</span>
      </div>

      <div className="audit-table-wrap">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Actor</th>
              <th>Method</th>
              <th>Path</th>
              <th>Status</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((event) => (
              <tr key={event.id}>
                <td>{new Date(event.created_at).toLocaleString()}</td>
                <td>{event.actor_email || "Unknown"}</td>
                <td><span className={`audit-method ${event.method.toLowerCase()}`}>{event.method}</span></td>
                <td><code>{event.path}</code></td>
                <td>{event.status_code ?? "—"}</td>
                <td>{event.ip_address || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {!filtered.length && !working && (
          <div className="empty-state">No audit events match the selected filters.</div>
        )}
      </div>
    </section>
  );
}
