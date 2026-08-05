import React, { useEffect, useMemo, useState } from "react";
import { apiRequest } from "./api";
import { BRAND } from "./brand";
import { FeatureHub } from "./featureHub";
import "./styles.build005.css";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { IntegrationHealth } from "./integrations";
import "./styles.integrations.css";
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

type SearchItem = {
  type: string;
  id: string;
  title: string;
  subtitle: string;
  status: string;
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
};

type LiveSummary = {
  status: string;
  active_outages: number;
  customers_affected: number;
  open_tickets: number;
  uisp: Record<string, unknown>;
  tauc: Record<string, unknown>;
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
        <h1>NAB MISSION CONTROL</h1>
        <p className="muted">Secure network operations access</p>

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

function CustomerSearch({
  token,
  onSelect
}: {
  token: string;
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchItem[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (query.trim().length < 2) {
      setItems([]);
      return;
    }

    const timer = window.setTimeout(async () => {
      setWorking(true);
      setError("");

      try {
        const result = await apiRequest<{
          items: SearchItem[];
        }>(`/search?q=${encodeURIComponent(query.trim())}`, {}, token);
        setItems(result.items);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Search failed");
      } finally {
        setWorking(false);
      }
    }, 300);

    return () => window.clearTimeout(timer);
  }, [query, token]);

  return (
    <section className="panel customer-search">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">GLOBAL SEARCH</p>
          <h3>Find a customer</h3>
        </div>
        <span>{working ? "Searching…" : `${items.length} results`}</span>
      </div>

      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Name, email, phone, account number…"
      />

      {error && <div className="error-message">{error}</div>}

      <div className="search-results">
        {items.map((item) => (
          <button key={item.id} onClick={() => onSelect(item.id)}>
            <div>
              <strong>{item.title}</strong>
              <span>{item.subtitle || `UISP #${item.id}`}</span>
            </div>
            <small>{item.status}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function CustomerView({
  token,
  clientId,
  onClose
}: {
  token: string;
  clientId: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<Customer360 | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");

    apiRequest<Customer360>(`/platform/customers/${clientId}/workspace`, {}, token)
      .then(setData)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Unable to load customer")
      );
  }, [clientId, token]);

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
              <p className="eyebrow">TAUC GATEWAY</p>
              <h3>Gateway identity</h3>
            </div>
          </div>
          {data.gateway ? (
            <div className="readiness-list">
              <div><span>Model</span><strong>{String(device.deviceModel || "Unavailable")}</strong></div>
              <div><span>Serial</span><strong>{String(device.sn || "Unavailable")}</strong></div>
              <div><span>MAC</span><strong>{String(device.mac || "Unavailable")}</strong></div>
              <div><span>Firmware</span><strong>{String(device.fwVersion || "Unavailable")}</strong></div>
              <div><span>Network</span><strong>{String(network.networkName || network.id || "Unavailable")}</strong></div>
            </div>
          ) : (
            <p className="muted">{data.gateway_error || "No TAUC gateway resolved."}</p>
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
            <span>Portal v2</span>
          </div>
        </div>

        <nav>
          {[
            ["⌂", "Mission Control"],
            ["◉", "Customers"],
            ["⌁", "Managed WiFi"],
            ["⌘", "Network"],
            ["⌬", "Network Intelligence"],
            ["⌇", "Fiber"],
            ["⌖", "Fiber Map"],
            ["!", "Outages"],
            ["⚠", "Alerts"],
            ["⚒", "Field Operations"],
            ["$", "Billing"],
            ["▣", "Inventory"],
            ["↗", "Analytics"],
            ["✓", "Audit"],
            ["⇄", "Integrations"],
            ["◎", "Customer Portal"],
            ["⚙", "Settings"]
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
            <h1>NAB MISSION CONTROL</h1>
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
          />
        ) : activePage === "Fiber Map" ? (
          <FiberMap token={token} />
        ) : activePage === "Fiber" ? (
          <FiberOperations token={token} />
        ) : activePage === "Integrations" ? (
          <IntegrationHealth token={token} />
        ) : activePage === "Network" ? (
          <NetworkOperationsCenter token={token} />
        ) : activePage === "Network Intelligence" ? (
          <FeatureHub token={token} mode="network" />
        ) : activePage === "Billing" ? (
          <BillingCenter token={token} />
        ) : activePage === "Alerts" ? (
          <AlertCenter token={token} />
        ) : activePage === "Audit" ? (
          <AuditCenter token={token} />
        ) : activePage === "Field Operations" ? (
          <FeatureHub token={token} mode="field" />
        ) : activePage === "Inventory" ? (
          <OperationsWorkspace token={token} />
        ) : activePage === "Outages" ? (
          <FeatureHub token={token} mode="outages" />
        ) : activePage === "Analytics" ? (
          <FeatureHub token={token} mode="reports" />
        ) : activePage === "Managed WiFi" ? (
          <FeatureHub token={token} mode="wifi" />
        ) : activePage === "Customer Portal" ? (
          <FeatureHub token={token} mode="portal" />
        ) : activePage === "Settings" ? (
          <FeatureHub token={token} mode="admin" />
        ) : activePage !== "Mission Control" && activePage !== "Customers" ? (
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
          <>
            <section className="hero-panel">
              <div>
                <p className="eyebrow">LIVE OPERATIONS</p>
                <h2>North Alabama Broadband Network</h2>
                <p>UISP, TAUC, Customer 360, and live telemetry are integrated.</p>
              </div>
              <span className="live-chip"><i /> {summary?.status || "Operational"}</span>
            </section>

            <section className="metrics">
              <Metric label="Network status" value={summary?.status || "Operational"} detail="Live integration health" />
              <Metric label="Active outages" value={String(summary?.active_outages ?? 0)} detail="Customer-impacting events" />
              <Metric label="Customers affected" value={String(summary?.customers_affected ?? 0)} detail="Current impact" />
              <Metric label="Open tickets" value={String(summary?.open_tickets ?? 0)} detail="Support workload" />
            </section>

            <div className="dashboard-grid">
              <CustomerSearch token={token} onSelect={(id) => {
                setActivePage("Customers");
                setSelectedClient(id);
              }} />

              <article className="panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">INTEGRATIONS</p>
                    <h3>Platform status</h3>
                  </div>
                </div>
                <div className="readiness-list">
                  <div><span>UISP</span><strong>{summary?.uisp?.connected ? "Connected" : "Unavailable"}</strong></div>
                  <div><span>TAUC</span><strong>{summary?.tauc?.configured ? "Configured" : "Not configured"}</strong></div>
                  <div><span>Customer 360</span><strong>Online</strong></div>
                  <div><span>Live WebSocket</span><strong>{liveState}</strong></div>
                </div>
              </article>
            </div>
          </>
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
