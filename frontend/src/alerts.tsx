import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type Alert = {
  id: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "critical";
  source: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  created_at: string;
};


export function AlertCenter({ token }: { token: string }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [severity, setSeverity] = useState("");
  const [showAcknowledged, setShowAcknowledged] = useState(false);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(true);

  const load = async () => {
    setWorking(true);
    setError("");

    try {
      const result = await request<Alert[]>(
        `/alerts?acknowledged=${showAcknowledged ? "true" : "false"}&limit=500`,
        token
      );
      setAlerts(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load alerts");
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    load();
  }, [token, showAcknowledged]);

  const filtered = useMemo(
    () => alerts.filter((alert) => !severity || alert.severity === severity),
    [alerts, severity]
  );

  const acknowledge = async (id: string) => {
    try {
      await request(`/alerts/${id}/acknowledge`, token, { method: "POST" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to acknowledge alert");
    }
  };

  const counts = useMemo(() => ({
    critical: alerts.filter((alert) => alert.severity === "critical").length,
    warning: alerts.filter((alert) => alert.severity === "warning").length,
    info: alerts.filter((alert) => alert.severity === "info").length
  }), [alerts]);

  return (
    <section className="alert-center">
      <div className="alert-center-header">
        <div>
          <p className="eyebrow">NAB MISSION CONTROL</p>
          <h2>Flight Alert Center</h2>
          <p>Review and acknowledge current network and platform alerts.</p>
        </div>
        <button onClick={load}>{working ? "Refreshing…" : "Refresh"}</button>
      </div>

      <div className="alert-metrics">
        <article><span>Critical</span><strong>{counts.critical}</strong></article>
        <article><span>Warning</span><strong>{counts.warning}</strong></article>
        <article><span>Informational</span><strong>{counts.info}</strong></article>
      </div>

      <div className="alert-filters">
        <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Informational</option>
        </select>

        <label>
          <input
            type="checkbox"
            checked={showAcknowledged}
            onChange={(event) => setShowAcknowledged(event.target.checked)}
          />
          Show acknowledged alerts
        </label>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="alert-list">
        {filtered.map((alert) => (
          <article className={`alert-card ${alert.severity}`} key={alert.id}>
            <div>
              <div>
                <strong>{alert.title}</strong>
                <span>{alert.source} · {new Date(alert.created_at).toLocaleString()}</span>
              </div>
              <span className={`alert-severity ${alert.severity}`}>{alert.severity}</span>
            </div>

            <p>{alert.message || "No additional alert details were provided."}</p>

            {alert.acknowledged ? (
              <small>
                Acknowledged by {alert.acknowledged_by || "administrator"}
                {alert.acknowledged_at
                  ? ` · ${new Date(alert.acknowledged_at).toLocaleString()}`
                  : ""}
              </small>
            ) : (
              <button onClick={() => acknowledge(alert.id)}>Acknowledge alert</button>
            )}
          </article>
        ))}

        {!filtered.length && !working && (
          <div className="empty-state">No alerts match the selected view.</div>
        )}
      </div>
    </section>
  );
}
