import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type Assignment = {
  id: string;
  client_id: string;
  device_id: string;
  serial_number: string;
  mac_address?: string | null;
  device_model?: string | null;
  network_id?: string | null;
  network_name?: string | null;
  firmware_version?: string | null;
  assigned_by: string;
  created_at: string;
  updated_at?: string;
};

type IntegrationStatus = {
  configured: boolean;
  base_url: string;
  certificate_present: boolean;
  private_key_present: boolean;
  access_key_configured: boolean;
  secret_key_configured: boolean;
  connected_devices_path?: string | null;
  minimum_request_interval_seconds: number;
  rate_limit_backoff_seconds: number;
  snapshot_cache_seconds: number;
  controls: {
    ssid_update: boolean;
    password_update: boolean;
    reboot: boolean;
    provider_diagnostics: boolean;
  };
};

type FleetResponse = {
  generated_at: string;
  integration: IntegrationStatus;
  summary: {
    assigned_gateways: number;
    managed_customers: number;
    known_networks: number;
    write_controls_ready: number;
  };
  items: Assignment[];
};

type GatewaySnapshot = {
  device_id: string;
  network_id?: string | null;
  network_name?: string | null;
  status: "ready" | "partial";
  device: Record<string, unknown>;
  wifi: Record<string, unknown>;
  wifi_networks: Record<string, unknown>[];
  connected_devices: Record<string, unknown>[];
  connected_devices_source: string;
  connected_devices_endpoint_configured: boolean;
  warnings: string[];
  provider_diagnostics_configured?: boolean;
  provider_diagnostics?: unknown;
};

type DiagnosticsResponse = { result: GatewaySnapshot };
type Tab = "overview" | "clients" | "controls" | "diagnostics";

function value(
  row: Record<string, unknown> | undefined,
  keys: string[],
  fallback = "—"
): string {
  for (const key of keys) {
    const candidate = row?.[key];
    if (candidate !== undefined && candidate !== null && candidate !== "") {
      return String(candidate);
    }
  }
  return fallback;
}

function signalValue(row: Record<string, unknown>): number | null {
  const raw = value(row, ["signal", "rssi", "signalStrength"], "");
  const parsed = Number.parseFloat(raw.replace(/[^\d.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function signalLabel(row: Record<string, unknown>): string {
  const signal = signalValue(row);
  if (signal === null) return "Signal unavailable";
  if (signal >= -55) return `${signal} dBm · excellent`;
  if (signal >= -67) return `${signal} dBm · good`;
  if (signal >= -75) return `${signal} dBm · fair`;
  return `${signal} dBm · weak`;
}

function Metric({
  label,
  reading,
  detail
}: {
  label: string;
  reading: string | number;
  detail: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>{reading}</strong>
      <small>{detail}</small>
    </article>
  );
}

export function ManagedWifiCenter({
  token,
  initialCustomerId = ""
}: {
  token: string;
  initialCustomerId?: string;
}) {
  const [fleet, setFleet] = useState<FleetResponse | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [snapshot, setSnapshot] = useState<GatewaySnapshot | null>(null);
  const [diagnostics, setDiagnostics] = useState<GatewaySnapshot | null>(null);
  const [query, setQuery] = useState("");
  const [clientQuery, setClientQuery] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [loadingFleet, setLoadingFleet] = useState(true);
  const [loadingSnapshot, setLoadingSnapshot] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [ssid, setSsid] = useState("");
  const [wifiPassword, setWifiPassword] = useState("");
  const [wifiPasswordConfirmation, setWifiPasswordConfirmation] = useState("");
  const [rebootConfirmation, setRebootConfirmation] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const loadFleet = async () => {
    setLoadingFleet(true);
    setError("");
    try {
      const next = await request<FleetResponse>("/tauc/fleet", token);
      setFleet(next);
      setSelectedId(current => (
        next.items.some(item => item.id === current)
          ? current
          : (
              next.items.find(item => item.client_id === initialCustomerId)?.id ||
              next.items[0]?.id ||
              ""
            )
      ));
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load managed Wi-Fi"
      );
    } finally {
      setLoadingFleet(false);
    }
  };

  useEffect(() => {
    void loadFleet();
  }, [token, initialCustomerId]);

  const selected = useMemo(
    () => fleet?.items.find(item => item.id === selectedId) || null,
    [fleet, selectedId]
  );

  useEffect(() => {
    setSsid("");
    setWifiPassword("");
    setWifiPasswordConfirmation("");
    setRebootConfirmation("");
    setDiagnostics(null);
    setMessage("");
    setError("");
    if (!selected) {
      setSnapshot(null);
      return;
    }

    let active = true;
    const parameters = new URLSearchParams();
    if (selected.network_id) parameters.set("network_id", selected.network_id);
    if (selected.network_name) parameters.set("network_name", selected.network_name);
    if (selected.serial_number) parameters.set("serial_number", selected.serial_number);
    if (selected.mac_address) parameters.set("mac_address", selected.mac_address);
    setLoadingSnapshot(true);
    request<GatewaySnapshot>(
      `/tauc/devices/${encodeURIComponent(selected.device_id)}/snapshot?${parameters}`,
      token
    )
      .then(result => {
        if (active) setSnapshot(result);
      })
      .catch(caught => {
        if (active) {
          setSnapshot(null);
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to read the selected gateway"
          );
        }
      })
      .finally(() => {
        if (active) setLoadingSnapshot(false);
      });
    return () => {
      active = false;
    };
  }, [refreshKey, selected, token]);

  const filteredFleet = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return fleet?.items || [];
    return (fleet?.items || []).filter(item => [
      item.client_id,
      item.serial_number,
      item.mac_address,
      item.device_model,
      item.network_id,
      item.network_name
    ].some(candidate => String(candidate || "").toLowerCase().includes(normalized)));
  }, [fleet, query]);

  const filteredClients = useMemo(() => {
    const normalized = clientQuery.trim().toLowerCase();
    const clients = snapshot?.connected_devices || [];
    if (!normalized) return clients;
    return clients.filter(row => [
      value(row, ["name", "hostName", "hostname", "alias"], ""),
      value(row, ["ip", "ipAddress", "ipv4"], ""),
      value(row, ["mac", "macAddress", "mac_address"], ""),
      value(row, ["band", "radio", "frequency"], "")
    ].some(candidate => candidate.toLowerCase().includes(normalized)));
  }, [clientQuery, snapshot]);

  const weakClients = (snapshot?.connected_devices || []).filter(row => {
    const signal = signalValue(row);
    return signal !== null && signal < -75;
  }).length;

  const controlBody = (extra: Record<string, unknown> = {}) => ({
    device_id: selected?.device_id,
    network_id: selected?.network_id || null,
    ...extra
  });

  const perform = async (
    label: string,
    path: string,
    body: Record<string, unknown>
  ) => {
    setBusy(label);
    setError("");
    setMessage("");
    try {
      await request(path, token, {
        method: "POST",
        body: JSON.stringify(body)
      });
      setMessage(`${label} completed successfully.`);
      setRefreshKey(current => current + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `${label} failed`);
    } finally {
      setBusy("");
    }
  };

  const runDiagnostics = async () => {
    if (!selected) return;
    setBusy("diagnostics");
    setError("");
    setMessage("");
    try {
      const response = await request<DiagnosticsResponse>(
        "/tauc/controls/diagnostics",
        token,
        {
          method: "POST",
          body: JSON.stringify({
            device_id: selected.device_id,
            network_id: selected.network_id || null,
            network_name: selected.network_name || null,
            serial_number: selected.serial_number,
            mac_address: selected.mac_address || null
          })
        }
      );
      setDiagnostics(response.result);
      setMessage("Gateway diagnostics completed.");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Gateway diagnostics failed"
      );
    } finally {
      setBusy("");
    }
  };

  const controls = fleet?.integration.controls;

  return (
    <section className="managed-wifi-center">
      <header className="managed-wifi-header">
        <div>
          <p className="eyebrow">SUBSCRIBER EXPERIENCE · RC1 BUILD 028</p>
          <h2>Managed Wi‑Fi Operations</h2>
          <p>
            Assigned TAUC gateways, wireless networks, connected devices, service
            diagnostics, and guarded customer controls in one NOC workspace.
          </p>
        </div>
        <div className="managed-wifi-header-actions">
          <span className={
            "managed-wifi-state " +
            (fleet?.integration.configured ? "ready" : "missing")
          }>
            {fleet?.integration.configured ? "TAUC configured" : "TAUC setup required"}
          </span>
          <button onClick={() => void loadFleet()} disabled={loadingFleet}>
            {loadingFleet ? "Refreshing fleet…" : "Refresh assignments"}
          </button>
        </div>
      </header>

      {error && <div className="error-message">{error}</div>}
      {message && <div className="dispatch-message">{message}</div>}

      {fleet && (
        <div className="managed-wifi-metrics">
          <Metric
            label="Assigned gateways"
            reading={fleet.summary.assigned_gateways}
            detail="Durable customer assignments"
          />
          <Metric
            label="Managed customers"
            reading={fleet.summary.managed_customers}
            detail="Unique UISP customer IDs"
          />
          <Metric
            label="Known networks"
            reading={fleet.summary.known_networks}
            detail="Resolved TAUC network IDs"
          />
          <Metric
            label="Controls ready"
            reading={`${fleet.summary.write_controls_ready} / 3`}
            detail="SSID, password, and reboot"
          />
          <Metric
            label="TAUC pacing"
            reading={`${fleet.integration.minimum_request_interval_seconds}s`}
            detail="Minimum interval per transaction"
          />
        </div>
      )}

      {fleet && !fleet.integration.configured && (
        <article className="managed-wifi-activation">
          <p className="eyebrow">SECURE ACTIVATION</p>
          <h3>Complete the TAUC credentials and mTLS configuration</h3>
          <p>
            Access key, secret key, client certificate, and private key must all
            be available to the API container. Credentials are never sent to this
            page.
          </p>
        </article>
      )}

      <div className="managed-wifi-layout">
        <aside className="managed-wifi-fleet">
          <div>
            <p className="eyebrow">GATEWAY FLEET</p>
            <h3>Customer assignments</h3>
          </div>
          <input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Customer ID, network, serial, MAC…"
          />
          <div className="managed-wifi-fleet-list">
            {filteredFleet.map(item => (
              <button
                key={item.id}
                className={item.id === selectedId ? "selected" : ""}
                onClick={() => setSelectedId(item.id)}
              >
                <span className="wifi-beacon" />
                <span>
                  <strong>{item.network_name || item.device_model || "TAUC gateway"}</strong>
                  <small>Customer {item.client_id}</small>
                  <em>{item.serial_number}</em>
                </span>
              </button>
            ))}
            {!filteredFleet.length && (
              <p className="muted">
                {fleet?.items.length
                  ? "No assigned gateways match this search."
                  : "Assign a TAUC gateway in Customer 360 to manage it here."}
              </p>
            )}
          </div>
        </aside>

        <main className="managed-wifi-workspace">
          {selected ? (
            <>
              <section className="managed-gateway-hero">
                <div>
                  <p className="eyebrow">SELECTED GATEWAY</p>
                  <h3>{selected.network_name || selected.device_model || "TAUC gateway"}</h3>
                  <p>
                    Customer {selected.client_id} · SN {selected.serial_number}
                  </p>
                </div>
                <div>
                  <span className={
                    "gateway-snapshot-state " +
                    (snapshot?.status === "ready" ? "ready" : "partial")
                  }>
                    {loadingSnapshot
                      ? "Reading TAUC…"
                      : snapshot?.status || "Unavailable"}
                  </span>
                  <button
                    disabled={loadingSnapshot || Boolean(busy)}
                    onClick={() => setRefreshKey(current => current + 1)}
                  >
                    Refresh live data
                  </button>
                </div>
              </section>

              <nav className="managed-wifi-tabs">
                {([
                  ["overview", "Overview"],
                  ["clients", `Clients (${snapshot?.connected_devices.length || 0})`],
                  ["controls", "Controls"],
                  ["diagnostics", "Diagnostics"]
                ] as [Tab, string][]).map(([key, label]) => (
                  <button
                    key={key}
                    className={tab === key ? "active" : ""}
                    onClick={() => setTab(key)}
                  >
                    {label}
                  </button>
                ))}
              </nav>

              {snapshot?.warnings.map(warning => (
                <p className="managed-wifi-warning" key={warning}>{warning}</p>
              ))}

              {tab === "overview" && (
                <div className="managed-wifi-overview">
                  <div className="managed-device-metrics">
                    <Metric
                      label="Model"
                      reading={value(snapshot?.device, ["deviceModel", "model"], selected.device_model || "—")}
                      detail={value(snapshot?.device, ["deviceType", "productType"], "TAUC gateway")}
                    />
                    <Metric
                      label="Firmware"
                      reading={value(snapshot?.device, ["fwVersion", "firmwareVersion", "softwareVersion"], selected.firmware_version || "—")}
                      detail="Reported by TAUC"
                    />
                    <Metric
                      label="Wi‑Fi networks"
                      reading={snapshot?.wifi_networks.length || 0}
                      detail="Configured radios and SSIDs"
                    />
                    <Metric
                      label="Connected clients"
                      reading={snapshot?.connected_devices.length || 0}
                      detail={`${weakClients} weak signal`}
                    />
                  </div>
                  <section className="managed-wifi-panel">
                    <div className="managed-wifi-panel-heading">
                      <div>
                        <p className="eyebrow">WIRELESS NETWORKS</p>
                        <h3>SSIDs and radios</h3>
                      </div>
                      <span>{snapshot?.wifi_networks.length || 0} returned</span>
                    </div>
                    <div className="wifi-network-grid">
                      {(snapshot?.wifi_networks || []).map((network, index) => (
                        <article key={value(network, ["id", "ssid", "ssidName"], String(index))}>
                          <span className="wifi-radio-icon">⌁</span>
                          <div>
                            <strong>{value(network, ["ssid", "ssidName", "name", "wifiName"], "Wi‑Fi network")}</strong>
                            <small>
                              {value(network, ["band", "frequency", "radio"], "Band unavailable")} · channel{" "}
                              {value(network, ["channel", "channelNumber"], "auto")}
                            </small>
                          </div>
                          <em>{value(network, ["enabled", "status"], "available")}</em>
                        </article>
                      ))}
                      {!snapshot?.wifi_networks.length && (
                        <p className="muted">No Wi‑Fi networks were returned by TAUC.</p>
                      )}
                    </div>
                  </section>
                </div>
              )}

              {tab === "clients" && (
                <section className="managed-wifi-panel">
                  <div className="managed-wifi-panel-heading">
                    <div>
                      <p className="eyebrow">CONNECTED DEVICES</p>
                      <h3>Subscriber network clients</h3>
                    </div>
                    <span>{snapshot?.connected_devices_source || "unavailable"}</span>
                  </div>
                  <input
                    className="client-filter"
                    value={clientQuery}
                    onChange={event => setClientQuery(event.target.value)}
                    placeholder="Filter by name, IP, MAC, or band…"
                  />
                  <div className="managed-client-list">
                    {filteredClients.map((client, index) => {
                      const signal = signalValue(client);
                      return (
                        <article key={value(client, ["id", "mac", "macAddress"], String(index))}>
                          <span className={
                            "client-signal " +
                            (signal === null ? "unknown" : signal < -75 ? "weak" : "good")
                          } />
                          <div>
                            <strong>{value(client, ["name", "hostName", "hostname", "alias", "mac"], "Connected device")}</strong>
                            <small>
                              {value(client, ["ip", "ipAddress", "ipv4"], "IP unavailable")} ·{" "}
                              {value(client, ["mac", "macAddress", "mac_address"], "MAC unavailable")}
                            </small>
                          </div>
                          <div>
                            <span>{value(client, ["band", "radio", "frequency"], "Wi‑Fi")}</span>
                            <small>{signalLabel(client)}</small>
                          </div>
                        </article>
                      );
                    })}
                    {!filteredClients.length && (
                      <p className="muted">No connected devices match this view.</p>
                    )}
                  </div>
                </section>
              )}

              {tab === "controls" && (
                <div className="managed-control-grid">
                  <form onSubmit={event => {
                    event.preventDefault();
                    void perform(
                      "Wi‑Fi name update",
                      "/tauc/controls/wifi/ssid",
                      controlBody({ value: ssid.trim() })
                    ).then(() => setSsid(""));
                  }}>
                    <p className="eyebrow">SSID</p>
                    <h3>Change Wi‑Fi name</h3>
                    <input
                      required
                      maxLength={32}
                      value={ssid}
                      onChange={event => setSsid(event.target.value)}
                      placeholder="New network name"
                    />
                    <button disabled={!controls?.ssid_update || Boolean(busy)}>
                      {busy === "Wi‑Fi name update" ? "Applying…" : "Apply Wi‑Fi name"}
                    </button>
                    <small>
                      {controls?.ssid_update
                        ? "Configured and permission checked."
                        : "Configure TAUC_WIFI_SSID_UPDATE_PATH to enable."}
                    </small>
                  </form>

                  <form onSubmit={event => {
                    event.preventDefault();
                    if (wifiPassword !== wifiPasswordConfirmation) {
                      setError("Wi‑Fi password confirmation does not match.");
                      return;
                    }
                    void perform(
                      "Wi‑Fi password update",
                      "/tauc/controls/wifi/password",
                      controlBody({ value: wifiPassword })
                    ).then(() => {
                      setWifiPassword("");
                      setWifiPasswordConfirmation("");
                    });
                  }}>
                    <p className="eyebrow">SECURITY</p>
                    <h3>Rotate Wi‑Fi password</h3>
                    <input
                      required
                      minLength={8}
                      maxLength={64}
                      type="password"
                      autoComplete="new-password"
                      value={wifiPassword}
                      onChange={event => setWifiPassword(event.target.value)}
                      placeholder="New password"
                    />
                    <input
                      required
                      minLength={8}
                      maxLength={64}
                      type="password"
                      autoComplete="new-password"
                      value={wifiPasswordConfirmation}
                      onChange={event => setWifiPasswordConfirmation(event.target.value)}
                      placeholder="Confirm password"
                    />
                    <button disabled={!controls?.password_update || Boolean(busy)}>
                      {busy === "Wi‑Fi password update" ? "Applying…" : "Rotate password"}
                    </button>
                    <small>
                      Password values are submitted once and never returned or stored.
                    </small>
                  </form>

                  <form className="danger-control" onSubmit={event => {
                    event.preventDefault();
                    if (rebootConfirmation !== "REBOOT") return;
                    void perform(
                      "Gateway reboot",
                      "/tauc/controls/reboot",
                      controlBody()
                    ).then(() => setRebootConfirmation(""));
                  }}>
                    <p className="eyebrow">DISRUPTIVE ACTION</p>
                    <h3>Reboot customer gateway</h3>
                    <p>
                      This temporarily interrupts all traffic on this managed gateway.
                    </p>
                    <input
                      value={rebootConfirmation}
                      onChange={event => setRebootConfirmation(event.target.value)}
                      placeholder="Type REBOOT to confirm"
                    />
                    <button
                      disabled={
                        !controls?.reboot ||
                        rebootConfirmation !== "REBOOT" ||
                        Boolean(busy)
                      }
                    >
                      {busy === "Gateway reboot" ? "Sending…" : "Reboot gateway"}
                    </button>
                    <small>
                      {controls?.reboot
                        ? "Explicit confirmation is required."
                        : "Configure TAUC_REBOOT_PATH to enable."}
                    </small>
                  </form>
                </div>
              )}

              {tab === "diagnostics" && (
                <section className="managed-wifi-panel diagnostics-panel">
                  <div className="managed-wifi-panel-heading">
                    <div>
                      <p className="eyebrow">SERVICE DIAGNOSTICS</p>
                      <h3>Gateway and network inspection</h3>
                    </div>
                    <button disabled={Boolean(busy)} onClick={() => void runDiagnostics()}>
                      {busy === "diagnostics" ? "Running…" : "Run diagnostics"}
                    </button>
                  </div>
                  <p className="muted">
                    Portal diagnostics use the saved network identity and the same
                    rate-limited TAUC request queue. Provider diagnostics run only
                    when their tenant endpoint is configured.
                  </p>
                  {diagnostics && (
                    <>
                      <div className="diagnostic-metrics">
                        <Metric label="Result" reading={diagnostics.status} detail="TAUC snapshot state" />
                        <Metric label="Network ID" reading={diagnostics.network_id || "—"} detail={diagnostics.network_name || "Unresolved"} />
                        <Metric label="Clients" reading={diagnostics.connected_devices.length} detail={diagnostics.connected_devices_source} />
                        <Metric label="Provider test" reading={diagnostics.provider_diagnostics_configured ? "Configured" : "Optional"} detail="Tenant-specific endpoint" />
                      </div>
                      {!!diagnostics.warnings.length && (
                        <ul className="diagnostic-warnings">
                          {diagnostics.warnings.map(warning => <li key={warning}>{warning}</li>)}
                        </ul>
                      )}
                      {diagnostics.provider_diagnostics !== undefined && (
                        <details>
                          <summary>Provider diagnostic response</summary>
                          <pre>{JSON.stringify(diagnostics.provider_diagnostics, null, 2)}</pre>
                        </details>
                      )}
                    </>
                  )}
                </section>
              )}

              <footer className="managed-wifi-footnote">
                <span>Customer {selected.client_id}</span>
                <span>Device {selected.device_id}</span>
                <span>{selected.mac_address || "MAC unavailable"}</span>
                <span>One TAUC transaction at a time</span>
              </footer>
            </>
          ) : (
            <section className="managed-wifi-empty">
              <h3>Select an assigned gateway</h3>
              <p>
                Customer gateway assignments remain managed in Customer 360 and
                automatically appear in this fleet.
              </p>
            </section>
          )}
        </main>
      </div>
    </section>
  );
}
