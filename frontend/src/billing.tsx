import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type Invoice = {
  id: string;
  number: string;
  client_id: string;
  client_name: string;
  due_date?: string;
  status: string;
  amount_due: number;
  overdue: boolean;
};

type Payment = {
  id: string;
  client_id: string;
  client_name: string;
  amount: number;
  method: string;
  created_at?: string;
};

type BillingSummary = {
  customers: number;
  open_invoices: number;
  overdue_invoices: number;
  outstanding_total: number;
  overdue_total: number;
  invoices: Invoice[];
  payments: Payment[];
};


function money(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  }).format(value || 0);
}

export function BillingCenter({ token }: { token: string }) {
  const [data, setData] = useState<BillingSummary | null>(null);
  const [tab, setTab] = useState<"invoices" | "payments">("invoices");
  const [query, setQuery] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setWorking(true);
    setError("");

    try {
      setData(await request<BillingSummary>("/billing-center/summary", token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load billing data");
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    load();
  }, [token]);

  const invoices = useMemo(() => {
    if (!data) return [];

    const needle = query.trim().toLowerCase();

    return data.invoices.filter((invoice) => {
      const matchesQuery =
        !needle ||
        `${invoice.number} ${invoice.client_name} ${invoice.client_id} ${invoice.status}`
          .toLowerCase()
          .includes(needle);

      return matchesQuery && (!overdueOnly || invoice.overdue);
    });
  }, [data, query, overdueOnly]);

  const payments = useMemo(() => {
    if (!data) return [];

    const needle = query.trim().toLowerCase();

    return data.payments.filter((payment) =>
      !needle ||
      `${payment.client_name} ${payment.client_id} ${payment.method}`
        .toLowerCase()
        .includes(needle)
    );
  }, [data, query]);

  const exportVisible = () => {
    const rows =
      tab === "invoices"
        ? invoices.map((invoice) => [
            invoice.number,
            invoice.client_name,
            invoice.client_id,
            invoice.due_date || "",
            invoice.status,
            invoice.amount_due,
            invoice.overdue ? "Yes" : "No"
          ])
        : payments.map((payment) => [
            payment.id,
            payment.client_name,
            payment.client_id,
            payment.created_at || "",
            payment.method,
            payment.amount
          ]);

    const header =
      tab === "invoices"
        ? ["Invoice", "Customer", "Client ID", "Due Date", "Status", "Amount Due", "Overdue"]
        : ["Payment ID", "Customer", "Client ID", "Date", "Method", "Amount"];

    const csv = [header, ...rows]
      .map((row) =>
        row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(",")
      )
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `nab-billing-${tab}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="billing-center">
      <div className="billing-header">
        <div>
          <p className="eyebrow">FINANCIAL OPERATIONS</p>
          <h2>Billing Center</h2>
          <p>Review UISP invoices, outstanding balances, and recent payments.</p>
        </div>
        <div className="billing-actions">
          <button onClick={load}>{working ? "Refreshing…" : "Refresh"}</button>
          <button onClick={exportVisible}>Export CSV</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="billing-metrics">
        <article><span>Customers</span><strong>{data?.customers ?? 0}</strong></article>
        <article><span>Open invoices</span><strong>{data?.open_invoices ?? 0}</strong></article>
        <article><span>Overdue invoices</span><strong>{data?.overdue_invoices ?? 0}</strong></article>
        <article><span>Outstanding</span><strong>{money(data?.outstanding_total ?? 0)}</strong></article>
        <article><span>Overdue total</span><strong>{money(data?.overdue_total ?? 0)}</strong></article>
      </div>

      <div className="billing-controls">
        <div className="billing-tabs">
          <button className={tab === "invoices" ? "active" : ""} onClick={() => setTab("invoices")}>
            Invoices
          </button>
          <button className={tab === "payments" ? "active" : ""} onClick={() => setTab("payments")}>
            Payments
          </button>
        </div>

        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search customer, account, invoice, method…"
        />

        {tab === "invoices" && (
          <label>
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(event) => setOverdueOnly(event.target.checked)}
            />
            Overdue only
          </label>
        )}
      </div>

      <div className="billing-table-wrap">
        {tab === "invoices" ? (
          <table className="billing-table">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Customer</th>
                <th>Due date</th>
                <th>Status</th>
                <th>Amount due</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => (
                <tr key={invoice.id || String(invoice.number)}>
                  <td><strong>#{invoice.number}</strong><small>Client {invoice.client_id}</small></td>
                  <td>{invoice.client_name}</td>
                  <td>{invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : "Unavailable"}</td>
                  <td><span className={invoice.overdue ? "billing-status overdue" : "billing-status"}>{invoice.status}</span></td>
                  <td>{money(invoice.amount_due)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="billing-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Customer</th>
                <th>Method</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((payment) => (
                <tr key={payment.id}>
                  <td>{payment.created_at ? new Date(payment.created_at).toLocaleString() : "Unavailable"}</td>
                  <td><strong>{payment.client_name}</strong><small>Client {payment.client_id}</small></td>
                  <td>{payment.method}</td>
                  <td>{money(payment.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!working && tab === "invoices" && !invoices.length && (
          <div className="empty-state">No invoices match the selected filters.</div>
        )}
        {!working && tab === "payments" && !payments.length && (
          <div className="empty-state">No payments match the selected filters.</div>
        )}
      </div>
    </section>
  );
}
