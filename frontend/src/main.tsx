import React, { useEffect, useMemo, useState } from "react";
import { apiRequest } from "./api";
import { BRAND } from "./brand";
import { FeatureHub } from "./featureHub";
import "./styles.build005.css";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { IntegrationHealth } from "./integrations";
import "./styles.integrations.css";
import { MikroTikOperations } from "./mikrotik";
import "./styles.mikrotik.css";
import { ManagedWifiCenter } from "./managedWifi";
import "./styles.managed-wifi.css";
import { CustomersDirectory } from "./customersDirectory";
import "./styles.customers-directory.css";
import { MissionControlOverview } from "./missionControl";
import "./styles.mission-control.css";
import { FiberMap } from "./fiberMap";
import "./styles.milestone12map.css";
import { FiberOperations } from "./fiber";
import "./styles.milestone12.css";
import { NetworkOperationsCenter } from "./network";
import "./styles.milestone11.css";
import { BillingCenter } from "./billing";
import "./styles.milestone10.css";
import { AuditCenter } from "./audit";
import { AlertCenter } from "./alerts";
import "./styles.milestone9.css";
import "./styles.operations.css";
import { OperationsWorkspace } from "./operations";
import "./brand.css";

type User = {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
  permissions: string[];
  is_superuser: boolean;
};

type LoginResponse = {
  token: string;
  user: User;
};

type CustomerActivity = {
  id: string;
  kind: "note" | "ticket" | "workorder" | "device";
  title: string;
  detail: string;
  status: string;
  actor: string;
  occurred_at: string;
};

type TaucAssignment = {
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
};

type Customer360 = {
  client_id: string;
  name: string;
  email?: string;
  phone?: string;
  address?: string;
  status: {
    active: boolean;
    suspended: boolean;
    past_due: boolean;
  };
  billing: {
    balance?: number;
    outstanding?: number;
    last_payment?: Record<string, unknown> | null;
    payments: Record<string, unknown>[];
    invoices: Record<string, unknown>[];
  };
  services: Record<string, unknown>[];
  gateway?: {
    device?: Record<string, unknown>;
    network?: Record<string, unknown>;
  } | null;
  gateway_error?: string;
  support?: {
    tickets: Record<string, unknown>[];
    workorders: Record<string, unknown>[];
  };
  activity?: CustomerActivity[];
  tauc_devices?: TaucAssignment[];
};

type LiveSummary = {
  status: string;
  active_outages: number;
  customers_affected: number;
  open_tickets: number;
  uisp: Record<string, unknown>;
  tauc: Record<string, unknown>;
  mikrotik: Record<string, unknown>;
};

function LoginPage({
  onLogin
}: {
  onLogin: (token: string, user: User) => void;
}) {
  const [email, setEmail] = useState("admin@nabroadband.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setWorking(true);

    try {
      const result = await apiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      onLogin(result.token, result.user);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="brand-mark"><img src="/nab-logo.svg" alt="North Alabama Broadband" /></div>
        <p className="eyebrow">NORTH ALABAMA BROADBAND</p>
        <h1>{BRAND.product}</h1>
        <p className="muted">Secure access to the broadband flight deck</p>

        <form onSubmit={submit}>
          <label>
            <span>Administrator email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label>
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
            />
          </label>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={working}>
            {working ? "LAUNCHING…" : "VERIFY AND LAUNCH"}
          </button>
        </form>

        <small>{BRAND.tagline}</small>
      </section>
    </main>
  );
}

function CustomerView({
  token,
  clientId,
  onClose,
  onOpenManagedWifi
}: {
  token: string;
  clientId: string;
  onClose: () => void;
  onOpenManagedWifi: (clientId: string) => void;
}) {
  const [data, setData] = useState<Customer360 | null>(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionBusy, setActionBusy] = useState("");
  const [ticketSubject, setTicketSubject] = useState("");
  const [workTitle, setWorkTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [taucSerial, setTaucSerial] = useState("");
  const [taucMac, setTaucMac] = useState("");

  useEffect(() => {
    setData(null);
    setError("");

    apiRequest<Customer360>(`/platform/customers/${clientId}/workspace`, {}, token)
      .then(setData)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Unable to load customer")
      );
  }, [clientId, token]);

  const runAction = async (label: string, path: string, body: Record<string, unknown> = {}) => {
    setActionBusy(label); setActionError(""); setActionMessage("");
    try {
      await apiRequest(path, { method: "POST", body: JSON.stringify(body) }, token);
      setActionMessage(`${label} completed successfully.`);
      if (label === "Support ticket") setTicketSubject("");
      if (label === "Field work order") setWorkTitle("");
      const refreshed = await apiRequest<Customer360>(
        `/platform/customers/${clientId}/workspace`,
        {},
        token
      );
      setData(refreshed);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : `${label} failed`);
    } finally {
      setActionBusy("");
    }
  };

  const addNote = async (event: React.FormEvent) => {
    event.preventDefault();
    const body = noteBody.trim();
    if (!body) return;
    setActionBusy("Account note"); setActionError(""); setActionMessage("");
    try {
      await apiRequest(
        `/platform/customers/${clientId}/notes`,
        { method: "POST", body: JSON.stringify({ body }) },
        token
      );
      setNoteBody("");
      setData(await apiRequest<Customer360>(
        `/platform/customers/${clientId}/workspace`,
        {},
        token
      ));
      setActionMessage("Account note added to the customer timeline.");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to add account note");
    } finally {
      setActionBusy("");
    }
  };

  const assignTaucDevice = async (event: React.FormEvent) => {
    event.preventDefault();
    setActionBusy("TAUC assignment"); setActionError(""); setActionMessage("");
    try {
      await apiRequest(
        `/customers/${clientId}/gateway/resolve`,
        {
          method: "POST",
          body: JSON.stringify({
            client_id: clientId,
            serial_number: taucSerial.trim(),
            mac_address: taucMac.trim()
          })
        },
        token
      );
      setTaucSerial("");
      setTaucMac("");
      setData(await apiRequest<Customer360>(
        `/platform/customers/${clientId}/workspace`,
        {},
        token
      ));
      setActionMessage("TAUC device assigned to this customer.");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to assign TAUC device");
    } finally {
      setActionBusy("");
    }
  };

  const removeTaucDevice = async (assignment: TaucAssignment) => {
    if (!window.confirm(`Remove TAUC device ${assignment.serial_number} from this customer?`)) return;
    setActionBusy(`Remove ${assignment.id}`); setActionError(""); setActionMessage("");
    try {
      await apiRequest(
        `/customers/${clientId}/gateways/${assignment.id}`,
        { method: "DELETE" },
        token
      );
      setData(await apiRequest<Customer360>(
        `/platform/customers/${clientId}/workspace`,
        {},
        token
      ));
      setActionMessage("TAUC device removed from this customer.");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to remove TAUC device");
    } finally {
      setActionBusy("");
    }
  };

  if (error) {
    return (
      <section className="panel customer360">
        <button onClick={onClose}>← Back</button>
        <div className="error-message">{error}</div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="panel customer360">
        <p>Loading Customer 360…</p>
      </section>
    );
  }

  const device = data.gateway?.device || {};
  const network = data.gateway?.network || {};
  const deviceId = String(device.deviceId || device.id || device.device_id || "");

  return (
    <section className="customer360-shell">
      <div className="customer360-hero">
        <div>
          <button className="link-button" onClick={onClose}>← Back to search</button>
          <p className="eyebrow">CUSTOMER 360</p>
          <h2>{data.name}</h2>
          <p>{data.email || "No email"} · {data.phone || "No phone"}</p>
          <p>{data.address || "No service address"}</p>
        </div>
        <div className="status-group">
          <span className={data.status.active ? "good" : "bad"}>
            {data.status.active ? "Active" : "Inactive"}
          </span>
          {data.status.suspended && <span className="bad">Suspended</span>}
          {data.status.past_due && <span className="warn">Past due</span>}
        </div>
      </div>

      <div className="metrics">
        <Metric label="UISP ID" value={data.client_id} detail="Customer account" />
        <Metric
          label="Balance"
          value={money(data.billing.balance)}
          detail="Current balance"
        />
        <Metric
          label="Outstanding"
          value={money(data.billing.outstanding)}
          detail="Amount due"
        />
        <Metric
          label="Services"
          value={String(data.services.length)}
          detail="Provisioned services"
        />
      </div>

      <section className="customer-action-center">
        <div className="panel-heading"><div><p className="eyebrow">CUSTOMER ACTION CENTER</p><h3>Resolve service from one workspace</h3></div></div>
        {actionError && <div className="error-message">{actionError}</div>}
        {actionMessage && <div className="dispatch-message">{actionMessage}</div>}
        <div className="customer-action-grid">
          <form onSubmit={(event) => { event.preventDefault(); runAction("Support ticket", "/tickets", { client_id: data.client_id, subject: ticketSubject, description: `Opened from Customer 360 for ${data.name}`, priority: "high" }); }}>
            <h4>Open support ticket</h4>
            <input required minLength={3} value={ticketSubject} onChange={event => setTicketSubject(event.target.value)} placeholder="Issue summary" />
            <button disabled={Boolean(actionBusy)}>{actionBusy === "Support ticket" ? "Opening…" : "Open ticket"}</button>
          </form>
          <form onSubmit={(event) => { event.preventDefault(); runAction("Field work order", "/workorders", { client_id: data.client_id, title: workTitle, description: `Dispatched from Customer 360 for ${data.name}`, priority: "high", service_address: data.address || null }); }}>
            <h4>Dispatch field work</h4>
            <input required minLength={3} value={workTitle} onChange={event => setWorkTitle(event.target.value)} placeholder="Work required" />
            <button disabled={Boolean(actionBusy)}>{actionBusy === "Field work order" ? "Dispatching…" : "Create work order"}</button>
          </form>
          <div className="gateway-actions">
            <h4>Managed Wi‑Fi</h4>
            <p>
              Live clients, wireless networks, diagnostics, and gateway controls
              are centralized in Managed Wi‑Fi.
            </p>
            <button
              type="button"
              disabled={!data.tauc_devices?.length}
              onClick={() => onOpenManagedWifi(data.client_id)}
            >
              Open Managed Wi‑Fi
            </button>
          </div>
        </div>
        <p className="muted">TAUC write actions remain permission-checked and configuration-gated by verified tenant endpoint paths.</p>
      </section>

      <section className="customer-timeline panel">
        <div className="panel-heading">
          <div><p className="eyebrow">ACCOUNT HISTORY</p><h3>Customer activity timeline</h3></div>
          <span>{data.activity?.length ?? 0} events</span>
        </div>
        <form className="timeline-note-form" onSubmit={addNote}>
          <textarea required maxLength={2000} value={noteBody} onChange={event => setNoteBody(event.target.value)} placeholder="Add an internal account note visible to portal staff…" />
          <button disabled={Boolean(actionBusy)}>{actionBusy === "Account note" ? "Saving…" : "Add note"}</button>
        </form>
        <div className="timeline-list">
          {(data.activity || []).map(item => <article className={`timeline-item ${item.kind}`} key={`${item.kind}-${item.id}`}>
            <span className="timeline-marker" aria-hidden="true" />
            <div>
              <header><strong>{item.title}</strong><time dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString()}</time></header>
              <p>{item.detail}</p>
              <footer>{item.actor || "System"}{item.status ? ` · ${item.status.replaceAll("_", " ")}` : ""}</footer>
            </div>
          </article>)}
          {!data.activity?.length && <p className="muted">No account activity has been recorded yet.</p>}
        </div>
      </section>

      <div className="dashboard-grid">
        <article className="panel large">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">SERVICE INTELLIGENCE</p>
              <h3>Internet services</h3>
            </div>
          </div>
          <div className="readiness-list">
            {data.services.length ? data.services.map((service, index) => (
              <div key={index}>
                <span>{String(service.name || service.plan || service.servicePlan || "Internet service")}</span>
                <strong>{String(service.status || service.speed || "Available")}</strong>
              </div>
            )) : <p className="muted">No services returned.</p>}
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">TAUC DEVICES</p>
              <h3>Customer assignments</h3>
            </div>
            <span>{data.tauc_devices?.length ?? 0} assigned</span>
          </div>
          <form className="tauc-assignment-form" onSubmit={assignTaucDevice}>
            <input
              required
              minLength={4}
              maxLength={128}
              value={taucSerial}
              onChange={event => setTaucSerial(event.target.value)}
              placeholder="TAUC serial number"
            />
            <input
              required
              maxLength={32}
              value={taucMac}
              onChange={event => setTaucMac(event.target.value)}
              placeholder="Device MAC address"
            />
            <button disabled={Boolean(actionBusy)}>
              {actionBusy === "TAUC assignment" ? "Verifying…" : "Verify and assign"}
            </button>
          </form>
          <div className="tauc-assignment-list">
            {(data.tauc_devices || []).map(assignment => (
              <div className="tauc-assignment" key={assignment.id}>
                <div>
                  <strong>{assignment.device_model || "TAUC gateway"}</strong>
                  <span>SN {assignment.serial_number} · {assignment.mac_address || "MAC unavailable"}</span>
                  <small>{assignment.network_name || assignment.network_id || "Network unavailable"}</small>
                </div>
                <button
                  type="button"
                  className="danger-action"
                  disabled={Boolean(actionBusy)}
                  onClick={() => removeTaucDevice(assignment)}
                >
                  {actionBusy === `Remove ${assignment.id}` ? "Removing…" : "Remove"}
                </button>
              </div>
            ))}
          </div>
          {data.gateway ? (
            <div className="readiness-list">
              <div><span>Model</span><strong>{String(device.deviceModel || "Unavailable")}</strong></div>
              <div><span>Serial</span><strong>{String(device.sn || "Unavailable")}</strong></div>
              <div><span>MAC</span><strong>{String(device.mac || "Unavailable")}</strong></div>
              <div><span>Firmware</span><strong>{String(device.fwVersion || "Unavailable")}</strong></div>
              <div><span>Network</span><strong>{String(network.networkName || network.networkId || network.id || "Unavailable")}</strong></div>
            </div>
          ) : (
            <p className="muted">{data.gateway_error || "No TAUC gateway resolved."}</p>
          )}
          {!!data.tauc_devices?.length && (
            <button
              type="button"
              className="customer-managed-wifi-link"
              onClick={() => onOpenManagedWifi(data.client_id)}
            >
              Open live Wi‑Fi networks, clients, diagnostics, and controls →
            </button>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">BILLING</p>
              <h3>Recent activity</h3>
            </div>
          </div>
          <div className="readiness-list">
            <div><span>Payments</span><strong>{data.billing.payments.length}</strong></div>
            <div><span>Invoices</span><strong>{data.billing.invoices.length}</strong></div>
            <div><span>Last payment</span><strong>{describePayment(data.billing.last_payment)}</strong></div>
            <div><span>Support tickets</span><strong>{data.support?.tickets.length ?? 0}</strong></div>
            <div><span>Work orders</span><strong>{data.support?.workorders.length ?? 0}</strong></div>
          </div>
        </article>
      </div>
    </section>
  );
}

function Dashboard({
  token,
  user,
  onLogout
}: {
  token: string;
  user: User;
  onLogout: () => void;
}) {
  const [summary, setSummary] = useState<LiveSummary | null>(null);
  const [selectedClient, setSelectedClient] = useState<string | null>(null);
  const [managedWifiCustomerId, setManagedWifiCustomerId] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activePage, setActivePage] = useState("Mission Control");
  const [liveState, setLiveState] = useState("Connecting");

  useEffect(() => {
    const load = () => {
      apiRequest<LiveSummary>("/live/summary", {}, token)
        .then(setSummary)
        .catch(() => setSummary(null));
    };

    load();
    const interval = window.setInterval(load, 30000);
    return () => window.clearInterval(interval);
  }, [token]);

  useEffect(() => {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(
      `${scheme}://${window.location.host}/api/v2/live/ws`
    );

    socket.addEventListener("open", () => {
      setLiveState("Live");
      socket.send("subscribe");
    });

    socket.addEventListener("close", () => setLiveState("Disconnected"));
    socket.addEventListener("error", () => setLiveState("Unavailable"));

    return () => socket.close();
  }, []);

  const roleLabel = useMemo(
    () => user.roles.map((role) => role.replaceAll("_", " ")).join(", "),
    [user.roles]
  );

  return (
    <div className="app-shell">
      <aside className={sidebarOpen ? "sidebar open" : "sidebar"}>
        <div className="sidebar-brand">
          <div className="brand-mark small"><img src="/nab-logo.svg" alt="North Alabama Broadband" /></div>
          <div>
            <strong>MISSION CONTROL</strong>
            <span>Rocket City Operations</span>
          </div>
        </div>

        <nav>
          {[
            ["⌂", "Mission Control"],
            ["◆", "Incident Command"],
            ["◉", "Customers"],
            ["⌁", "Managed Wi-Fi"],
            ["⌘", "Network"],
            ["⌗", "MikroTik NOC"],
            ["⌬", "Network Telemetry"],
            ["⌇", "Fiber"],
            ["⌖", "Fiber Map"],
            ["!", "Outages"],
            ["⚠", "Flight Alerts"],
            ["⚒", "Ground Crew"],
            ["$", "Billing"],
            ["▣", "Operations Suite"],
            ["↗", "Mission Reports"],
            ["✓", "Audit"],
            ["⇄", "Systems Check"],
            ["◎", "Subscriber Portal"],
            ["≡", "Capability Parity"],
            ["⚙", "Access Control"]
          ].map(([icon, label]) => (
            <button
              key={label}
              className={activePage === label ? "active" : ""}
              onClick={() => {
                setActivePage(label);
                setSelectedClient(null);
                setSidebarOpen(false);
              }}
            >
              <span>{icon}</span>{label}
            </button>
          ))}
        </nav>

        <div className="sidebar-user">
          <strong>{user.display_name}</strong>
          <span>{user.email}</span>
          <small>{roleLabel}</small>
        </div>
      </aside>

      {sidebarOpen && (
        <button
          className="mobile-overlay"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation"
        />
      )}

      <main className="workspace">
        <header className="topbar">
          <button
            className="menu-button"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <div>
            <p className="eyebrow">BROADBAND FLIGHT OPERATIONS</p>
            <h1>{BRAND.product}</h1>
          </div>
          <div className="topbar-actions">
            <span className="live-chip"><i /> {liveState}</span>
            <button onClick={onLogout}>Sign out</button>
          </div>
        </header>

        {selectedClient ? (
          <CustomerView
            token={token}
            clientId={selectedClient}
            onClose={() => {
              setSelectedClient(null);
              setActivePage("Customers");
            }}
            onOpenManagedWifi={(clientId) => {
              setManagedWifiCustomerId(clientId);
              setSelectedClient(null);
              setActivePage("Managed Wi-Fi");
            }}
          />
        ) : activePage === "Incident Command" ? (
          <FeatureHub token={token} mode="incidents" />
        ) : activePage === "Fiber Map" ? (
          <FiberMap token={token} />
        ) : activePage === "Fiber" ? (
          <FiberOperations token={token} />
        ) : activePage === "Systems Check" ? (
          <IntegrationHealth token={token} />
        ) : activePage === "Network" ? (
          <NetworkOperationsCenter token={token} />
        ) : activePage === "MikroTik NOC" ? (
          <MikroTikOperations token={token} />
        ) : activePage === "Network Telemetry" ? (
          <FeatureHub token={token} mode="network" />
        ) : activePage === "Billing" ? (
          <BillingCenter token={token} />
        ) : activePage === "Flight Alerts" ? (
          <AlertCenter token={token} />
        ) : activePage === "Audit" ? (
          <AuditCenter token={token} />
        ) : activePage === "Ground Crew" ? (
          <FeatureHub token={token} mode="field" />
        ) : activePage === "Operations Suite" ? (
          <OperationsWorkspace token={token} />
        ) : activePage === "Outages" ? (
          <FeatureHub token={token} mode="outages" />
        ) : activePage === "Mission Reports" ? (
          <FeatureHub token={token} mode="reports" />
        ) : activePage === "Managed Wi-Fi" ? (
          <ManagedWifiCenter
            token={token}
            initialCustomerId={managedWifiCustomerId}
          />
        ) : activePage === "Subscriber Portal" ? (
          <FeatureHub token={token} mode="portal" />
        ) : activePage === "Capability Parity" ? (
          <FeatureHub token={token} mode="parity" />
        ) : activePage === "Access Control" ? (
          <FeatureHub token={token} mode="admin" />
        ) : activePage === "Customers" ? (
          <CustomersDirectory
            token={token}
            onSelect={(clientId) => setSelectedClient(clientId)}
          />
        ) : activePage !== "Mission Control" ? (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">NAB MISSION CONTROL</p>
                <h3>{activePage}</h3>
              </div>
            </div>
            <p className="muted">
              The {activePage} module is connected to navigation and ready for its
              next integration release.
            </p>
          </section>
        ) : (
          <MissionControlOverview
            token={token}
            liveSummary={summary}
            onNavigate={(page) => {
              setActivePage(page);
              setSelectedClient(null);
              setSidebarOpen(false);
            }}
          />
        )}
      </main>
    </div>
  );
}

function Metric({
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

function money(value?: number) {
  if (value === undefined || value === null) return "Unavailable";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  }).format(value);
}

function describePayment(payment?: Record<string, unknown> | null) {
  if (!payment) return "None";
  const amount = payment.amount || payment.amountPaid || payment.total;
  return amount ? String(amount) : "Available";
}

function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem("nab_v2_token") || ""
  );
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("nab_v2_user");
    return raw ? JSON.parse(raw) : null;
  });

  function login(nextToken: string, nextUser: User) {
    localStorage.setItem("nab_v2_token", nextToken);
    localStorage.setItem("nab_v2_user", JSON.stringify(nextUser));
    setToken(nextToken);
    setUser(nextUser);
  }

  async function logout() {
    try {
      await apiRequest<void>("/auth/logout", { method: "POST" }, token);
    } finally {
      localStorage.removeItem("nab_v2_token");
      localStorage.removeItem("nab_v2_user");
      setToken("");
      setUser(null);
    }
  }

  if (!token || !user) {
    return <LoginPage onLogin={login} />;
  }

  return <Dashboard token={token} user={user} onLogout={logout} />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
