import React, { useEffect, useState } from "react";
import { request } from "./api";

type Ticket = { id: string; client_id?: string; subject: string; status: string; priority: string; assigned_to?: string };
type WorkOrder = { id: string; client_id?: string; title: string; status: string; priority: string; assigned_technician?: string; service_address?: string };
type InventoryItem = { id: string; sku: string; name: string; category: string; quantity_on_hand: number; reorder_level: number; location?: string };
type Tab = "tickets" | "workorders" | "inventory";
const priorities = ["low", "normal", "high", "critical"];

export function OperationsWorkspace({ token }: { token: string }) {
  const [tab, setTab] = useState<Tab>("tickets");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [ticket, setTicket] = useState({ subject: "", description: "", client_id: "", priority: "normal", assigned_to: "" });
  const [order, setOrder] = useState({ title: "", description: "", client_id: "", priority: "normal", assigned_technician: "", service_address: "" });
  const [item, setItem] = useState({ sku: "", name: "", category: "General", quantity_on_hand: "0", reorder_level: "0", location: "" });

  const loadAll = async () => {
    const [nextTickets, nextOrders, nextInventory] = await Promise.all([
      request<Ticket[]>("/tickets", token), request<WorkOrder[]>("/workorders", token), request<InventoryItem[]>("/inventory", token)
    ]);
    setTickets(nextTickets); setOrders(nextOrders); setInventory(nextInventory);
  };

  function showError(caught: unknown) { setError(caught instanceof Error ? caught.message : "Unable to complete operation"); }
  useEffect(() => { loadAll().catch(showError); }, [token]);

  const perform = async (label: string, action: () => Promise<unknown>) => {
    setBusy(label); setError(""); setMessage("");
    try { await action(); await loadAll(); setMessage("Operation completed successfully."); }
    catch (caught) { showError(caught); }
    finally { setBusy(""); }
  };

  const createTicket = (event: React.FormEvent) => { event.preventDefault(); perform("ticket-create", async () => {
    await request("/tickets", token, { method: "POST", body: JSON.stringify({ ...ticket, client_id: ticket.client_id || null, assigned_to: ticket.assigned_to || null }) });
    setTicket({ subject: "", description: "", client_id: "", priority: "normal", assigned_to: "" });
  }); };
  const createOrder = (event: React.FormEvent) => { event.preventDefault(); perform("workorder-create", async () => {
    await request("/workorders", token, { method: "POST", body: JSON.stringify({ ...order, client_id: order.client_id || null, assigned_technician: order.assigned_technician || null, service_address: order.service_address || null }) });
    setOrder({ title: "", description: "", client_id: "", priority: "normal", assigned_technician: "", service_address: "" });
  }); };
  const createItem = (event: React.FormEvent) => { event.preventDefault(); perform("inventory-create", async () => {
    await request("/inventory", token, { method: "POST", body: JSON.stringify({ ...item, quantity_on_hand: Number(item.quantity_on_hand), reorder_level: Number(item.reorder_level), location: item.location || null, serial_tracking: "optional" }) });
    setItem({ sku: "", name: "", category: "General", quantity_on_hand: "0", reorder_level: "0", location: "" });
  }); };
  const patch = (path: string, status: string) => perform(path + status, () => request(path, token, { method: "PATCH", body: JSON.stringify({ status }) }));
  const adjust = (id: string, delta: number) => perform(id + delta, () => request(`/inventory/${id}/adjust`, token, { method: "POST", body: JSON.stringify({ delta }) }));

  return <section className="operations-shell">
    <div className="operations-header"><div><p className="eyebrow">V1 PARITY · SHARED OPERATIONS</p><h2>Tickets, Field Work & Inventory</h2></div><div className="operations-tabs">
      <button className={tab === "tickets" ? "active" : ""} onClick={() => setTab("tickets")}>Tickets</button><button className={tab === "workorders" ? "active" : ""} onClick={() => setTab("workorders")}>Work Orders</button><button className={tab === "inventory" ? "active" : ""} onClick={() => setTab("inventory")}>Inventory</button>
    </div></div>
    {error && <div className="error-message">{error}</div>}{message && <div className="dispatch-message">{message}</div>}

    {tab === "tickets" && <><form className="operations-form" onSubmit={createTicket}><h3>Create support ticket</h3>
      <input required minLength={3} placeholder="Subject" value={ticket.subject} onChange={e => setTicket({ ...ticket, subject: e.target.value })} /><input placeholder="Customer ID" value={ticket.client_id} onChange={e => setTicket({ ...ticket, client_id: e.target.value })} /><select value={ticket.priority} onChange={e => setTicket({ ...ticket, priority: e.target.value })}>{priorities.map(x => <option key={x}>{x}</option>)}</select><input placeholder="Assign to email" value={ticket.assigned_to} onChange={e => setTicket({ ...ticket, assigned_to: e.target.value })} /><textarea placeholder="Description" value={ticket.description} onChange={e => setTicket({ ...ticket, description: e.target.value })} /><button disabled={Boolean(busy)}>{busy === "ticket-create" ? "Creating…" : "Create ticket"}</button>
    </form><div className="operations-grid">{tickets.map(row => <article className="operation-card" key={row.id}><div><span className={`priority ${row.priority}`}>{row.priority}</span><small>{row.status}</small></div><h3>{row.subject}</h3><p>{row.client_id ? `Client ${row.client_id}` : "No customer linked"}</p><footer>{row.assigned_to || "Unassigned"}</footer><div className="card-actions"><button onClick={() => patch(`/tickets/${row.id}`, "in_progress")}>Start</button><button onClick={() => patch(`/tickets/${row.id}`, "resolved")}>Resolve</button><button onClick={() => patch(`/tickets/${row.id}`, "closed")}>Close</button></div></article>)}</div></>}

    {tab === "workorders" && <><form className="operations-form" onSubmit={createOrder}><h3>Create work order</h3>
      <input required minLength={3} placeholder="Title" value={order.title} onChange={e => setOrder({ ...order, title: e.target.value })} /><input placeholder="Customer ID" value={order.client_id} onChange={e => setOrder({ ...order, client_id: e.target.value })} /><select value={order.priority} onChange={e => setOrder({ ...order, priority: e.target.value })}>{priorities.map(x => <option key={x}>{x}</option>)}</select><input placeholder="Technician email" value={order.assigned_technician} onChange={e => setOrder({ ...order, assigned_technician: e.target.value })} /><input placeholder="Service address" value={order.service_address} onChange={e => setOrder({ ...order, service_address: e.target.value })} /><textarea placeholder="Work instructions" value={order.description} onChange={e => setOrder({ ...order, description: e.target.value })} /><button disabled={Boolean(busy)}>{busy === "workorder-create" ? "Creating…" : "Create work order"}</button>
    </form><div className="operations-grid">{orders.map(row => <article className="operation-card" key={row.id}><div><span className={`priority ${row.priority}`}>{row.priority}</span><small>{row.status}</small></div><h3>{row.title}</h3><p>{row.service_address || "No service address"}</p><footer>{row.assigned_technician || "Unassigned"}</footer><div className="card-actions"><button onClick={() => patch(`/workorders/${row.id}`, "scheduled")}>Schedule</button><button onClick={() => patch(`/workorders/${row.id}`, "in_progress")}>Start</button><button onClick={() => patch(`/workorders/${row.id}`, "completed")}>Complete</button></div></article>)}</div></>}

    {tab === "inventory" && <><form className="operations-form" onSubmit={createItem}><h3>Add inventory item</h3>
      <input required placeholder="SKU" value={item.sku} onChange={e => setItem({ ...item, sku: e.target.value })} /><input required minLength={2} placeholder="Item name" value={item.name} onChange={e => setItem({ ...item, name: e.target.value })} /><input placeholder="Category" value={item.category} onChange={e => setItem({ ...item, category: e.target.value })} /><input type="number" min="0" placeholder="Quantity" value={item.quantity_on_hand} onChange={e => setItem({ ...item, quantity_on_hand: e.target.value })} /><input type="number" min="0" placeholder="Reorder level" value={item.reorder_level} onChange={e => setItem({ ...item, reorder_level: e.target.value })} /><input placeholder="Location" value={item.location} onChange={e => setItem({ ...item, location: e.target.value })} /><button disabled={Boolean(busy)}>{busy === "inventory-create" ? "Adding…" : "Add inventory"}</button>
    </form><div className="operations-grid">{inventory.map(row => { const low = row.quantity_on_hand <= row.reorder_level; return <article className="operation-card" key={row.id}><div><span className={low ? "priority critical" : "priority normal"}>{low ? "low stock" : row.category}</span><small>{row.sku}</small></div><h3>{row.name}</h3><p>{row.location || "No location"}</p><footer>{row.quantity_on_hand} on hand</footer><div className="card-actions"><button onClick={() => adjust(row.id, -1)} disabled={row.quantity_on_hand === 0}>−1</button><button onClick={() => adjust(row.id, 1)}>+1</button><button onClick={() => adjust(row.id, 10)}>+10</button></div></article>; })}</div></>}
  </section>;
}
