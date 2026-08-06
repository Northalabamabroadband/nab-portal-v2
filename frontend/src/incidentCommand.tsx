import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type IncidentTab = "outages" | "tickets" | "workorders";

type Outage = {
  id: string;
  site_name: string;
  devices: Array<{ id?: string; name: string }>;
  customers_affected: number;
  severity: string;
  alert_count: number;
  recommended_action: string;
  response_ready: boolean;
  ticket_id?: string | null;
  workorder_id?: string | null;
};

type Ticket = {
  id: string;
  client_id?: string | null;
  subject: string;
  description: string;
  status: string;
  priority: string;
  assigned_to?: string | null;
  incident_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type WorkOrder = {
  id: string;
  client_id?: string | null;
  title: string;
  description: string;
  status: string;
  priority: string;
  assigned_technician?: string | null;
  service_address?: string | null;
  scheduled_for?: string | null;
  incident_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type IncidentCommandData = {
  generated_at: string;
  mission_state: "critical" | "degraded" | "nominal";
  network_error?: string | null;
  summary: {
    active_incidents: number;
    customers_affected: number;
    unacknowledged_alerts: number;
    critical_alerts: number;
    open_tickets: number;
    urgent_tickets: number;
    active_workorders: number;
    unassigned_workorders: number;
  };
  incidents: Outage[];
  tickets: Ticket[];
  workorders: WorkOrder[];
};

const ticketStatuses = [
  "open",
  "pending",
  "in_progress",
  "resolved",
  "closed",
];
const workOrderStatuses = [
  "open",
  "scheduled",
  "in_progress",
  "completed",
  "cancelled",
];
const priorities = ["low", "normal", "high", "critical", "urgent"];

export function IncidentCommand({
  token,
  permissions,
  onOpenCustomer,
  onNavigate,
}: {
  token: string;
  permissions: string[];
  onOpenCustomer: (clientId: string) => void;
  onNavigate: (page: string) => void;
}) {
  const [data, setData] = useState<IncidentCommandData | null>(null);
  const [tab, setTab] = useState<IncidentTab>("outages");
  const [query, setQuery] = useState("");
  const [working, setWorking] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const canManageTickets = permissions.includes("customers.write");
  const canManageWork = permissions.includes("network.write");

  async function refresh() {
    setWorking(true);
    setError("");
    try {
      setData(
        await request<IncidentCommandData>(
          "/platform/incidents/command",
          token,
        ),
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load Incident Command",
      );
    } finally {
      setWorking(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [token]);

  async function perform(
    actionKey: string,
    successMessage: string,
    path: string,
    options: RequestInit,
  ) {
    setBusy(actionKey);
    setError("");
    setMessage("");
    try {
      await request(path, token, options);
      await refresh();
      setMessage(successMessage);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to complete incident action",
      );
    } finally {
      setBusy("");
    }
  }

  async function dispatch(outage: Outage) {
    setBusy(`dispatch-${outage.id}`);
    setError("");
    setMessage("");
    try {
      const result = await request<{
        created: string[];
        reopened: string[];
        idempotent: boolean;
      }>(
        `/platform/incidents/${outage.id}/dispatch`,
        token,
        { method: "POST" },
      );
      await refresh();
      setMessage(
        result.created.length
          ? `Response package created: ${result.created.join(" and ")}.`
          : result.reopened.length
            ? `Response package reopened: ${result.reopened.join(" and ")}.`
            : "The response package was already active; no duplicate records were created.",
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to dispatch outage response",
      );
    } finally {
      setBusy("");
    }
  }

  const normalizedQuery = query.trim().toLowerCase();
  const outages = useMemo(
    () => (data?.incidents || []).filter((outage) =>
      searchable(
        normalizedQuery,
        outage.site_name,
        outage.id,
        outage.devices.map((device) => device.name).join(" "),
      )
    ),
    [data?.incidents, normalizedQuery],
  );
  const tickets = useMemo(
    () => (data?.tickets || []).filter((ticket) =>
      searchable(
        normalizedQuery,
        ticket.subject,
        ticket.description,
        ticket.client_id,
        ticket.assigned_to,
        ticket.incident_id,
      )
    ),
    [data?.tickets, normalizedQuery],
  );
  const workorders = useMemo(
    () => (data?.workorders || []).filter((order) =>
      searchable(
        normalizedQuery,
        order.title,
        order.description,
        order.client_id,
        order.assigned_technician,
        order.service_address,
        order.incident_id,
      )
    ),
    [data?.workorders, normalizedQuery],
  );

  return (
    <section className="incident-command">
      <header className={`incident-command-header command-${data?.mission_state || "degraded"}`}>
        <div>
          <p className="eyebrow">OPERATIONS RESPONSE · RC1 BUILD 031</p>
          <h2>Incident Command</h2>
          <p>
            Triage live outages and manage every open support ticket and field
            work order from one shared command queue.
          </p>
        </div>
        <div className="incident-header-actions">
          <span className={`command-state state-${data?.mission_state || "degraded"}`}>
            <i />
            {display(data?.mission_state || "degraded")}
          </span>
          <button type="button" onClick={() => void refresh()} disabled={working}>
            {working ? "Refreshing…" : "Refresh command"}
          </button>
        </div>
      </header>

      {error && <div className="error-message">{error}</div>}
      {message && <div className="dispatch-message">{message}</div>}
      {data?.network_error && (
        <div className="incident-network-warning">
          <strong>UISP NMS outage telemetry is temporarily unavailable.</strong>
          <span>{data.network_error}</span>
          <small>Tickets and work orders remain manageable.</small>
        </div>
      )}

      <div className="incident-command-metrics">
        <CommandMetric
          label="Active outages"
          value={data?.summary.active_incidents ?? 0}
          detail={`${data?.summary.customers_affected ?? 0} customers affected`}
          tone={(data?.summary.active_incidents ?? 0) ? "critical" : "normal"}
        />
        <CommandMetric
          label="Open tickets"
          value={data?.summary.open_tickets ?? 0}
          detail={`${data?.summary.urgent_tickets ?? 0} high or critical`}
        />
        <CommandMetric
          label="Active work orders"
          value={data?.summary.active_workorders ?? 0}
          detail={`${data?.summary.unassigned_workorders ?? 0} unassigned`}
        />
        <CommandMetric
          label="Critical alerts"
          value={data?.summary.critical_alerts ?? 0}
          detail={`${data?.summary.unacknowledged_alerts ?? 0} awaiting acknowledgment`}
          tone={(data?.summary.critical_alerts ?? 0) ? "critical" : "normal"}
        />
      </div>

      <section className="incident-queue">
        <div className="incident-queue-toolbar">
          <div className="incident-tabs" role="tablist" aria-label="Command queues">
            <QueueTab
              active={tab === "outages"}
              count={data?.incidents.length ?? 0}
              label="Outages"
              onClick={() => setTab("outages")}
            />
            <QueueTab
              active={tab === "tickets"}
              count={data?.tickets.length ?? 0}
              label="Open tickets"
              onClick={() => setTab("tickets")}
            />
            <QueueTab
              active={tab === "workorders"}
              count={data?.workorders.length ?? 0}
              label="Work orders"
              onClick={() => setTab("workorders")}
            />
          </div>
          <label className="incident-search">
            <span>Filter command queue</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Site, customer, assignee, incident, or work…"
            />
          </label>
        </div>

        {tab === "outages" && (
          <div className="outage-command-grid">
            {outages.map((outage) => (
              <article className="outage-command-card" key={outage.id}>
                <header>
                  <span className={`incident-priority priority-${outage.severity}`}>
                    {outage.severity}
                  </span>
                  <small>Incident {outage.id}</small>
                </header>
                <h3>{outage.site_name}</h3>
                <div className="outage-impact">
                  <span><strong>{outage.devices.length}</strong> offline devices</span>
                  <span><strong>{outage.customers_affected}</strong> customers affected</span>
                  <span><strong>{outage.alert_count}</strong> linked alerts</span>
                </div>
                <div className="outage-device-list">
                  {outage.devices.map((device, index) => (
                    <span key={`${device.id || device.name}-${index}`}>
                      <i />{device.name}
                    </span>
                  ))}
                </div>
                <p>{outage.recommended_action}</p>
                {outage.response_ready && (
                  <div className="response-package">
                    <strong>Response package active</strong>
                    <span>Ticket {shortId(outage.ticket_id)}</span>
                    <span>Work order {shortId(outage.workorder_id)}</span>
                  </div>
                )}
                <button
                  className="dispatch-button"
                  type="button"
                  disabled={
                    Boolean(busy)
                    || outage.response_ready
                    || !canManageWork
                  }
                  onClick={() => void dispatch(outage)}
                >
                  {outage.response_ready
                    ? "Response package active"
                    : busy === `dispatch-${outage.id}`
                      ? "Dispatching…"
                      : "Create ticket + work order"}
                </button>
                {!canManageWork && (
                  <small className="permission-note">
                    Network write permission is required to dispatch.
                  </small>
                )}
              </article>
            ))}
            {!working && !outages.length && (
              <CommandEmpty
                title="No matching active outages"
                detail={
                  normalizedQuery
                    ? "Adjust the command queue filter."
                    : "UISP NMS reports no active device-offline incidents."
                }
              />
            )}
          </div>
        )}

        {tab === "tickets" && (
          <div className="incident-record-list">
            {tickets.map((ticket) => (
              <TicketCommandCard
                key={ticket.id}
                ticket={ticket}
                canManage={canManageTickets}
                busy={busy === `ticket-${ticket.id}`}
                onOpenCustomer={onOpenCustomer}
                onSave={(updates) => perform(
                  `ticket-${ticket.id}`,
                  `Ticket “${ticket.subject}” updated.`,
                  `/tickets/${ticket.id}`,
                  { method: "PATCH", body: JSON.stringify(updates) },
                )}
              />
            ))}
            {!working && !tickets.length && (
              <CommandEmpty
                title="No matching open tickets"
                detail="Resolved and closed tickets automatically leave this queue."
              />
            )}
          </div>
        )}

        {tab === "workorders" && (
          <div className="incident-record-list">
            {workorders.map((order) => (
              <WorkOrderCommandCard
                key={order.id}
                order={order}
                canManage={canManageWork}
                busy={busy === `workorder-${order.id}`}
                onOpenCustomer={onOpenCustomer}
                onSave={(updates) => perform(
                  `workorder-${order.id}`,
                  `Work order “${order.title}” updated.`,
                  `/workorders/${order.id}`,
                  { method: "PATCH", body: JSON.stringify(updates) },
                )}
              />
            ))}
            {!working && !workorders.length && (
              <CommandEmpty
                title="No matching active work orders"
                detail="Completed and cancelled work automatically leave this queue."
              />
            )}
          </div>
        )}
      </section>

      <footer className="incident-command-footer">
        <span>
          Live outages come from UISP NMS. Ticket and work-order changes use the
          same records as Customer 360, Ground Crew, and Operations Suite.
        </span>
        <button type="button" onClick={() => onNavigate("Operations Suite")}>
          Open full Operations Suite →
        </button>
      </footer>
    </section>
  );
}

function TicketCommandCard({
  ticket,
  canManage,
  busy,
  onOpenCustomer,
  onSave,
}: {
  ticket: Ticket;
  canManage: boolean;
  busy: boolean;
  onOpenCustomer: (clientId: string) => void;
  onSave: (updates: Record<string, unknown>) => void;
}) {
  const [status, setStatus] = useState(ticket.status);
  const [priority, setPriority] = useState(ticket.priority);
  const [assignee, setAssignee] = useState(ticket.assigned_to || "");

  useEffect(() => {
    setStatus(ticket.status);
    setPriority(ticket.priority);
    setAssignee(ticket.assigned_to || "");
  }, [ticket]);

  return (
    <article className="incident-record-card">
      <header>
        <div>
          <span className={`incident-priority priority-${priority}`}>{priority}</span>
          {ticket.incident_id && <span className="linked-incident">◆ {ticket.incident_id}</span>}
        </div>
        <small>{formatTime(ticket.updated_at || ticket.created_at)}</small>
      </header>
      <h3>{ticket.subject}</h3>
      <p>{cleanDescription(ticket.description)}</p>
      <div className="incident-record-context">
        <span>{ticket.client_id ? `Customer ${ticket.client_id}` : "No customer linked"}</span>
        <span>{ticket.assigned_to || "Unassigned"}</span>
        <span>Ticket {shortId(ticket.id)}</span>
      </div>
      <div className="incident-record-controls">
        <label>
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)} disabled={!canManage || busy}>
            {ticketStatuses.map((value) => <option value={value} key={value}>{display(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Priority</span>
          <select value={priority} onChange={(event) => setPriority(event.target.value)} disabled={!canManage || busy}>
            {priorities.map((value) => <option value={value} key={value}>{display(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Assigned to</span>
          <input value={assignee} onChange={(event) => setAssignee(event.target.value)} placeholder="Email or team" disabled={!canManage || busy} />
        </label>
        <button
          type="button"
          disabled={!canManage || busy}
          onClick={() => onSave({
            status,
            priority,
            assigned_to: assignee.trim() || null,
          })}
        >
          {busy ? "Saving…" : "Save ticket"}
        </button>
      </div>
      <div className="incident-record-links">
        {ticket.client_id && (
          <button type="button" onClick={() => onOpenCustomer(ticket.client_id!)}>
            Open Customer 360
          </button>
        )}
        {!canManage && <span>Customer write permission is required to update tickets.</span>}
      </div>
    </article>
  );
}

function WorkOrderCommandCard({
  order,
  canManage,
  busy,
  onOpenCustomer,
  onSave,
}: {
  order: WorkOrder;
  canManage: boolean;
  busy: boolean;
  onOpenCustomer: (clientId: string) => void;
  onSave: (updates: Record<string, unknown>) => void;
}) {
  const [status, setStatus] = useState(order.status);
  const [priority, setPriority] = useState(order.priority);
  const [technician, setTechnician] = useState(order.assigned_technician || "");
  const [scheduledFor, setScheduledFor] = useState(
    toLocalDateTime(order.scheduled_for),
  );

  useEffect(() => {
    setStatus(order.status);
    setPriority(order.priority);
    setTechnician(order.assigned_technician || "");
    setScheduledFor(toLocalDateTime(order.scheduled_for));
  }, [order]);

  return (
    <article className="incident-record-card">
      <header>
        <div>
          <span className={`incident-priority priority-${priority}`}>{priority}</span>
          {order.incident_id && <span className="linked-incident">◆ {order.incident_id}</span>}
        </div>
        <small>{formatTime(order.updated_at || order.created_at)}</small>
      </header>
      <h3>{order.title}</h3>
      <p>{cleanDescription(order.description)}</p>
      <div className="incident-record-context">
        <span>{order.service_address || "No service address"}</span>
        <span>{order.assigned_technician || "Unassigned"}</span>
        <span>Work order {shortId(order.id)}</span>
      </div>
      <div className="incident-record-controls workorder-controls">
        <label>
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)} disabled={!canManage || busy}>
            {workOrderStatuses.map((value) => <option value={value} key={value}>{display(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Priority</span>
          <select value={priority} onChange={(event) => setPriority(event.target.value)} disabled={!canManage || busy}>
            {priorities.map((value) => <option value={value} key={value}>{display(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Technician</span>
          <input value={technician} onChange={(event) => setTechnician(event.target.value)} placeholder="Email or crew" disabled={!canManage || busy} />
        </label>
        <label>
          <span>Scheduled for</span>
          <input type="datetime-local" value={scheduledFor} onChange={(event) => setScheduledFor(event.target.value)} disabled={!canManage || busy} />
        </label>
        <button
          type="button"
          disabled={!canManage || busy}
          onClick={() => onSave({
            status,
            priority,
            assigned_technician: technician.trim() || null,
            scheduled_for: scheduledFor
              ? new Date(scheduledFor).toISOString()
              : null,
          })}
        >
          {busy ? "Saving…" : "Save work order"}
        </button>
      </div>
      <div className="incident-record-links">
        {order.client_id && (
          <button type="button" onClick={() => onOpenCustomer(order.client_id!)}>
            Open Customer 360
          </button>
        )}
        {!canManage && <span>Network write permission is required to update field work.</span>}
      </div>
    </article>
  );
}

function CommandMetric({
  label,
  value,
  detail,
  tone = "normal",
}: {
  label: string;
  value: number;
  detail: string;
  tone?: "normal" | "critical";
}) {
  return (
    <article className={`command-metric command-metric-${tone}`}>
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
      <small>{detail}</small>
    </article>
  );
}

function QueueTab({
  active,
  count,
  label,
  onClick,
}: {
  active: boolean;
  count: number;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={active ? "active" : ""}
      onClick={onClick}
      role="tab"
      aria-selected={active}
    >
      <span>{label}</span>
      <strong>{count}</strong>
    </button>
  );
}

function CommandEmpty({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="incident-command-empty">
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function searchable(query: string, ...values: Array<string | null | undefined>) {
  if (!query) return true;
  return values.some((value) => String(value || "").toLowerCase().includes(query));
}

function display(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortId(value?: string | null) {
  if (!value) return "pending";
  return value.length > 10 ? value.slice(0, 8) : value;
}

function cleanDescription(value: string) {
  return value.replace(/\[incident:[^\]]+\]\s*/gi, "").trim()
    || "No additional description.";
}

function formatTime(value?: string | null) {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : date.toLocaleString();
}

function toLocalDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
