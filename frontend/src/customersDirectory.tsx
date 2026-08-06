import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type CustomerStatus = {
  active: boolean;
  suspended: boolean;
  past_due: boolean;
  label: string;
};

type DirectoryCustomer = {
  id: string;
  name: string;
  account_number: string;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  status: CustomerStatus;
  balance?: number | null;
};

type DirectoryResponse = {
  query: string;
  offset: number;
  limit: number;
  count: number;
  has_more: boolean;
  summary: {
    visible: number;
    active: number;
    inactive: number;
    past_due: number;
  };
  items: DirectoryCustomer[];
};

type StatusFilter = "all" | "active" | "inactive" | "past_due";
type SortMode = "name" | "status" | "balance";

export function CustomersDirectory({
  token,
  onSelect,
}: {
  token: string;
  onSelect: (clientId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<DirectoryCustomer[]>([]);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortMode, setSortMode] = useState<SortMode>("name");
  const [hasMore, setHasMore] = useState(false);
  const [working, setWorking] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const trimmedQuery = query.trim();

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(async () => {
      setWorking(true);
      setError("");
      try {
        const search = trimmedQuery
          ? `?q=${encodeURIComponent(trimmedQuery)}&limit=250`
          : "?limit=250&offset=0";
        const result = await request<DirectoryResponse>(
          `/customers/directory${search}`,
          token,
        );
        if (active) {
          setItems(result.items);
          setHasMore(result.has_more);
        }
      } catch (caught) {
        if (active) {
          setItems([]);
          setHasMore(false);
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load customers",
          );
        }
      } finally {
        if (active) setWorking(false);
      }
    }, trimmedQuery ? 350 : 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [refreshKey, token, trimmedQuery]);

  const filteredItems = useMemo(() => {
    const rows = items.filter((customer) => {
      if (statusFilter === "active") return customer.status.active;
      if (statusFilter === "inactive") return !customer.status.active;
      if (statusFilter === "past_due") return customer.status.past_due;
      return true;
    });
    return rows.sort((left, right) => {
      if (sortMode === "balance") {
        return (right.balance ?? Number.NEGATIVE_INFINITY)
          - (left.balance ?? Number.NEGATIVE_INFINITY);
      }
      if (sortMode === "status") {
        return left.status.label.localeCompare(right.status.label)
          || left.name.localeCompare(right.name);
      }
      return left.name.localeCompare(right.name);
    });
  }, [items, sortMode, statusFilter]);

  const counts = useMemo(() => ({
    visible: items.length,
    active: items.filter((customer) => customer.status.active).length,
    inactive: items.filter((customer) => !customer.status.active).length,
    pastDue: items.filter((customer) => customer.status.past_due).length,
  }), [items]);

  async function loadMore() {
    if (!hasMore || loadingMore || trimmedQuery) return;
    setLoadingMore(true);
    setError("");
    try {
      const result = await request<DirectoryResponse>(
        `/customers/directory?limit=250&offset=${items.length}`,
        token,
      );
      setItems((current) => {
        const byId = new Map(current.map((customer) => [customer.id, customer]));
        result.items.forEach((customer) => byId.set(customer.id, customer));
        return Array.from(byId.values());
      });
      setHasMore(result.has_more);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load more customers",
      );
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <section className="customers-directory">
      <header className="customers-directory-header">
        <div>
          <p className="eyebrow">CUSTOMER OPERATIONS · RC1 BUILD 029</p>
          <h2>Customers</h2>
          <p>UISP CRM is the authoritative customer directory.</p>
        </div>
        <button
          type="button"
          onClick={() => setRefreshKey((key) => key + 1)}
          disabled={working}
        >
          {working ? "Refreshing…" : "Refresh customers"}
        </button>
      </header>

      <div className="customer-directory-metrics">
        <DirectoryMetric label="Loaded" value={counts.visible} detail="UISP CRM records" />
        <DirectoryMetric label="Active" value={counts.active} detail="Service active" />
        <DirectoryMetric label="Inactive" value={counts.inactive} detail="Inactive or suspended" />
        <DirectoryMetric label="Past due" value={counts.pastDue} detail="Explicit UISP status" />
      </div>

      <section className="customer-directory-controls" aria-label="Customer filters">
        <label className="customer-directory-search">
          <span>Search UISP CRM</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Name, email, phone, or account number…"
          />
        </label>
        <label>
          <span>Status</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
          >
            <option value="all">All customers</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="past_due">Past due</option>
          </select>
        </label>
        <label>
          <span>Sort</span>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as SortMode)}
          >
            <option value="name">Customer name</option>
            <option value="status">Account status</option>
            <option value="balance">Balance</option>
          </select>
        </label>
      </section>

      {error && <div className="error-message">{error}</div>}

      <section className="customer-directory-panel">
        <div className="customer-directory-caption">
          <div>
            <p className="eyebrow">CUSTOMER DIRECTORY</p>
            <h3>{working ? "Loading customers…" : `${filteredItems.length} customers shown`}</h3>
          </div>
          {trimmedQuery && <span>Search: “{trimmedQuery}”</span>}
        </div>

        <div className="customer-directory-table" role="table">
          <div className="customer-directory-row customer-directory-heading" role="row">
            <span>Customer</span>
            <span>Contact</span>
            <span>Service address</span>
            <span>Status</span>
            <span>Balance</span>
            <span aria-hidden="true" />
          </div>
          {filteredItems.map((customer) => (
            <button
              className="customer-directory-row"
              key={customer.id}
              type="button"
              onClick={() => onSelect(customer.id)}
              aria-label={`Open ${customer.name} in Customer 360`}
            >
              <span className="customer-primary">
                <strong>{customer.name}</strong>
                <small>Account {customer.account_number}</small>
              </span>
              <span className="customer-contact">
                <strong>{customer.email || "No email"}</strong>
                <small>{customer.phone || "No phone"}</small>
              </span>
              <span>{customer.address || "No address returned"}</span>
              <span>
                <i className={`customer-status customer-status-${statusClass(customer.status)}`}>
                  {customer.status.label}
                </i>
              </span>
              <span className="customer-balance">
                {formatBalance(customer.balance)}
              </span>
              <span className="customer-open-link">Open 360 →</span>
            </button>
          ))}
        </div>

        {!working && !filteredItems.length && !error && (
          <div className="customer-directory-empty">
            <strong>No matching customers</strong>
            <span>Adjust the search or account status filter.</span>
          </div>
        )}

        {hasMore && !trimmedQuery && (
          <button
            className="customer-load-more"
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
          >
            {loadingMore ? "Loading…" : "Load more customers"}
          </button>
        )}
      </section>
    </section>
  );
}

function DirectoryMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
      <small>{detail}</small>
    </article>
  );
}

function statusClass(status: CustomerStatus) {
  if (status.past_due) return "past-due";
  if (status.suspended) return "suspended";
  return status.active ? "active" : "inactive";
}

function formatBalance(balance?: number | null) {
  if (balance === null || balance === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(balance);
}
