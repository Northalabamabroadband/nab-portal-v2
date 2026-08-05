import React, { useEffect, useState } from "react";
import { request } from "./api";

type Ticket = {
  id: string;
  client_id?: string;
  subject: string;
  status: string;
  priority: string;
  assigned_to?: string;
};

type WorkOrder = {
  id: string;
  client_id?: string;
  title: string;
  status: string;
  priority: string;
  assigned_technician?: string;
  service_address?: string;
};

type InventoryItem = {
  id: string;
  sku: string;
  name: string;
  category: string;
  quantity_on_hand: number;
  reorder_level: number;
  location?: string;
};


export function OperationsWorkspace({ token }: { token: string }) {
  const [tab, setTab] = useState<"tickets" | "workorders" | "inventory">("tickets");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      request<Ticket[]>("/tickets", token),
      request<WorkOrder[]>("/workorders", token),
      request<InventoryItem[]>("/inventory", token)
    ])
      .then(([nextTickets, nextOrders, nextInventory]) => {
        setTickets(nextTickets);
        setOrders(nextOrders);
        setInventory(nextInventory);
      })
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Unable to load operations")
      );
  }, [token]);

  return (
    <section className="operations-shell">
      <div className="operations-header">
        <div>
          <p className="eyebrow">OPERATIONS SUITE</p>
          <h2>Tickets, Field Work & Inventory</h2>
        </div>
        <div className="operations-tabs">
          <button className={tab === "tickets" ? "active" : ""} onClick={() => setTab("tickets")}>Tickets</button>
          <button className={tab === "workorders" ? "active" : ""} onClick={() => setTab("workorders")}>Work Orders</button>
          <button className={tab === "inventory" ? "active" : ""} onClick={() => setTab("inventory")}>Inventory</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {tab === "tickets" && (
        <div className="operations-grid">
          {tickets.map((ticket) => (
            <article className="operation-card" key={ticket.id}>
              <div><span className={`priority ${ticket.priority}`}>{ticket.priority}</span><small>{ticket.status}</small></div>
              <h3>{ticket.subject}</h3>
              <p>{ticket.client_id ? `Client ${ticket.client_id}` : "No customer linked"}</p>
              <footer>{ticket.assigned_to || "Unassigned"}</footer>
            </article>
          ))}
          {!tickets.length && <div className="empty-state">No support tickets yet.</div>}
        </div>
      )}

      {tab === "workorders" && (
        <div className="operations-grid">
          {orders.map((order) => (
            <article className="operation-card" key={order.id}>
              <div><span className={`priority ${order.priority}`}>{order.priority}</span><small>{order.status}</small></div>
              <h3>{order.title}</h3>
              <p>{order.service_address || "No service address"}</p>
              <footer>{order.assigned_technician || "Unassigned"}</footer>
            </article>
          ))}
          {!orders.length && <div className="empty-state">No work orders yet.</div>}
        </div>
      )}

      {tab === "inventory" && (
        <div className="operations-grid">
          {inventory.map((item) => {
            const low = item.quantity_on_hand <= item.reorder_level;
            return (
              <article className="operation-card" key={item.id}>
                <div><span className={low ? "priority critical" : "priority normal"}>{low ? "low stock" : item.category}</span><small>{item.sku}</small></div>
                <h3>{item.name}</h3>
                <p>{item.location || "No location"}</p>
                <footer>{item.quantity_on_hand} on hand</footer>
              </article>
            );
          })}
          {!inventory.length && <div className="empty-state">No inventory items yet.</div>}
        </div>
      )}
    </section>
  );
}
