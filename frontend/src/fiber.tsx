import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type FiberAsset = {
  id: string;
  asset_type: string;
  name: string;
  asset_code: string;
  status: string;
  location_name?: string;
  manufacturer?: string;
  model?: string;
  serial_number?: string;
  strand_count?: number;
  used_capacity: number;
  total_capacity: number;
  client_id?: string;
};

type FiberRoute = {
  id: string;
  route_code: string;
  name: string;
  status: string;
  cable_type?: string;
  strand_count: number;
  length_feet: number;
  start_location?: string;
  end_location?: string;
};

type FiberSummary = {
  assets_total: number;
  routes_total: number;
  onts_total: number;
  splitters_total: number;
  assets_attention: number;
  used_capacity: number;
  total_capacity: number;
  available_capacity: number;
  utilization_percent: number;
};


export function FiberOperations({ token }: { token: string }) {
  const [assets, setAssets] = useState<FiberAsset[]>([]);
  const [routes, setRoutes] = useState<FiberRoute[]>([]);
  const [summary, setSummary] = useState<FiberSummary | null>(null);
  const [tab, setTab] = useState<"assets" | "routes" | "capacity">("assets");
  const [query, setQuery] = useState("");
  const [assetType, setAssetType] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(true);

  const load = async () => {
    setWorking(true);
    setError("");

    try {
      const [nextAssets, nextRoutes, nextSummary] = await Promise.all([
        request<FiberAsset[]>("/fiber/assets?limit=2000", token),
        request<FiberRoute[]>("/fiber/routes?limit=2000", token),
        request<FiberSummary>("/fiber/summary", token)
      ]);
      setAssets(nextAssets);
      setRoutes(nextRoutes);
      setSummary(nextSummary);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load fiber operations");
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    load();
  }, [token]);

  const filteredAssets = useMemo(() => {
    const needle = query.trim().toLowerCase();

    return assets.filter((asset) => {
      const haystack = [
        asset.name,
        asset.asset_code,
        asset.asset_type,
        asset.status,
        asset.location_name,
        asset.manufacturer,
        asset.model,
        asset.serial_number,
        asset.client_id
      ].join(" ").toLowerCase();

      return (
        (!needle || haystack.includes(needle)) &&
        (!assetType || asset.asset_type === assetType)
      );
    });
  }, [assets, assetType, query]);

  const filteredRoutes = useMemo(() => {
    const needle = query.trim().toLowerCase();

    return routes.filter((route) =>
      !needle ||
      [
        route.name,
        route.route_code,
        route.status,
        route.cable_type,
        route.start_location,
        route.end_location
      ].join(" ").toLowerCase().includes(needle)
    );
  }, [routes, query]);

  const exportVisible = () => {
    const rows =
      tab === "routes"
        ? filteredRoutes.map((route) => [
            route.route_code,
            route.name,
            route.status,
            route.cable_type || "",
            route.strand_count,
            route.length_feet,
            route.start_location || "",
            route.end_location || ""
          ])
        : filteredAssets.map((asset) => [
            asset.asset_code,
            asset.name,
            asset.asset_type,
            asset.status,
            asset.location_name || "",
            asset.manufacturer || "",
            asset.model || "",
            asset.serial_number || "",
            asset.used_capacity,
            asset.total_capacity
          ]);

    const header =
      tab === "routes"
        ? ["Route Code", "Name", "Status", "Cable Type", "Strands", "Length Feet", "Start", "End"]
        : ["Asset Code", "Name", "Type", "Status", "Location", "Manufacturer", "Model", "Serial", "Used", "Total"];

    const csv = [header, ...rows]
      .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `nab-fiber-${tab}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="fiber-center">
      <div className="fiber-header">
        <div>
          <p className="eyebrow">OUTSIDE PLANT OPERATIONS</p>
          <h2>Fiber Operations</h2>
          <p>Manage routes, cabinets, splitters, OLTs, ONTs, poles, handholes, and capacity.</p>
        </div>
        <div className="fiber-actions">
          <button onClick={load}>{working ? "Refreshing…" : "Refresh"}</button>
          <button onClick={exportVisible} disabled={tab === "capacity"}>Export CSV</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="fiber-metrics">
        <article><span>Assets</span><strong>{summary?.assets_total ?? 0}</strong></article>
        <article><span>Routes</span><strong>{summary?.routes_total ?? 0}</strong></article>
        <article><span>ONTs</span><strong>{summary?.onts_total ?? 0}</strong></article>
        <article><span>Splitters</span><strong>{summary?.splitters_total ?? 0}</strong></article>
        <article><span>Needs attention</span><strong>{summary?.assets_attention ?? 0}</strong></article>
        <article><span>Utilization</span><strong>{summary?.utilization_percent ?? 0}%</strong></article>
      </div>

      <div className="fiber-controls">
        <div className="fiber-tabs">
          <button className={tab === "assets" ? "active" : ""} onClick={() => setTab("assets")}>Assets</button>
          <button className={tab === "routes" ? "active" : ""} onClick={() => setTab("routes")}>Routes</button>
          <button className={tab === "capacity" ? "active" : ""} onClick={() => setTab("capacity")}>Capacity</button>
        </div>

        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search asset, code, location, route, serial…"
        />

        {tab === "assets" && (
          <select value={assetType} onChange={(event) => setAssetType(event.target.value)}>
            <option value="">All asset types</option>
            <option value="cabinet">Cabinets</option>
            <option value="pole">Poles</option>
            <option value="handhole">Handholes</option>
            <option value="vault">Vaults</option>
            <option value="splitter">Splitters</option>
            <option value="olt">OLTs</option>
            <option value="ont">ONTs</option>
            <option value="splice_enclosure">Splice enclosures</option>
            <option value="slack_loop">Slack loops</option>
            <option value="patch_panel">Patch panels</option>
            <option value="conduit">Conduit</option>
          </select>
        )}
      </div>

      {tab === "assets" && (
        <div className="fiber-table-wrap">
          <table className="fiber-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Asset</th>
                <th>Type</th>
                <th>Location</th>
                <th>Equipment</th>
                <th>Serial</th>
                <th>Capacity</th>
              </tr>
            </thead>
            <tbody>
              {filteredAssets.map((asset) => (
                <tr key={asset.id}>
                  <td><span className={`fiber-status ${asset.status}`}>{asset.status}</span></td>
                  <td><strong>{asset.name}</strong><small>{asset.asset_code}</small></td>
                  <td>{asset.asset_type.replaceAll("_", " ")}</td>
                  <td>{asset.location_name || "Unavailable"}</td>
                  <td>{[asset.manufacturer, asset.model].filter(Boolean).join(" ") || "—"}</td>
                  <td><code>{asset.serial_number || "—"}</code></td>
                  <td>{asset.used_capacity} / {asset.total_capacity}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!working && !filteredAssets.length && <div className="empty-state">No fiber assets match the selected filters.</div>}
        </div>
      )}

      {tab === "routes" && (
        <div className="fiber-table-wrap">
          <table className="fiber-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Route</th>
                <th>Cable</th>
                <th>Strands</th>
                <th>Length</th>
                <th>Start</th>
                <th>End</th>
              </tr>
            </thead>
            <tbody>
              {filteredRoutes.map((route) => (
                <tr key={route.id}>
                  <td><span className={`fiber-status ${route.status}`}>{route.status}</span></td>
                  <td><strong>{route.name}</strong><small>{route.route_code}</small></td>
                  <td>{route.cable_type || "—"}</td>
                  <td>{route.strand_count}</td>
                  <td>{route.length_feet.toLocaleString()} ft</td>
                  <td>{route.start_location || "—"}</td>
                  <td>{route.end_location || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!working && !filteredRoutes.length && <div className="empty-state">No fiber routes match the selected filters.</div>}
        </div>
      )}

      {tab === "capacity" && (
        <div className="fiber-capacity-grid">
          <article>
            <span>Total capacity</span>
            <strong>{summary?.total_capacity ?? 0}</strong>
            <small>Tracked ports, strands, or splitter positions</small>
          </article>
          <article>
            <span>Used capacity</span>
            <strong>{summary?.used_capacity ?? 0}</strong>
            <small>Assigned or occupied capacity</small>
          </article>
          <article>
            <span>Available capacity</span>
            <strong>{summary?.available_capacity ?? 0}</strong>
            <small>Remaining tracked capacity</small>
          </article>
          <article className="fiber-utilization-card">
            <div>
              <span>Overall utilization</span>
              <strong>{summary?.utilization_percent ?? 0}%</strong>
            </div>
            <i><b style={{ width: `${Math.min(summary?.utilization_percent ?? 0, 100)}%` }} /></i>
          </article>
        </div>
      )}
    </section>
  );
}
