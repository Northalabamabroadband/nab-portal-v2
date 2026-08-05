import React, { useEffect, useMemo, useRef, useState } from "react";
import { request } from "./api";

type PointFeature = {
  id: string;
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: {
    id: string;
    asset_type: string;
    name: string;
    asset_code: string;
    status: string;
    location_name?: string;
    manufacturer?: string;
    model?: string;
    serial_number?: string;
    client_id?: string;
    used_capacity: number;
    total_capacity: number;
  };
};

type LineFeature = {
  id: string;
  geometry: {
    type: "LineString";
    coordinates: [number, number][];
  };
  properties: {
    id: string;
    route_code: string;
    name: string;
    status: string;
    cable_type?: string;
    strand_count: number;
    length_feet: number;
    start_location?: string;
    end_location?: string;
    ownership?: string;
  };
};

type MapResponse = {
  assets: { features: PointFeature[] };
  routes: { features: LineFeature[] };
  summary: {
    mapped_assets: number;
    unmapped_assets: number;
    mapped_routes: number;
    unmapped_routes: number;
  };
  routes_without_geometry: {
    id: string;
    route_code: string;
    name: string;
    status: string;
  }[];
};

type Bounds = {
  minLon: number;
  maxLon: number;
  minLat: number;
  maxLat: number;
};


function calculateBounds(
  assets: PointFeature[],
  routes: LineFeature[]
): Bounds {
  const coordinates: [number, number][] = [
    ...assets.map((asset) => asset.geometry.coordinates),
    ...routes.flatMap((route) => route.geometry.coordinates)
  ];

  if (!coordinates.length) {
    return {
      minLon: -88.5,
      maxLon: -85.5,
      minLat: 33.8,
      maxLat: 35.2
    };
  }

  const longitudes = coordinates.map(([longitude]) => longitude);
  const latitudes = coordinates.map(([, latitude]) => latitude);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const lonPadding = Math.max((maxLon - minLon) * 0.12, 0.01);
  const latPadding = Math.max((maxLat - minLat) * 0.12, 0.01);

  return {
    minLon: minLon - lonPadding,
    maxLon: maxLon + lonPadding,
    minLat: minLat - latPadding,
    maxLat: maxLat + latPadding
  };
}

function assetSymbol(type: string) {
  const symbols: Record<string, string> = {
    cabinet: "C",
    pole: "P",
    handhole: "H",
    vault: "V",
    splitter: "S",
    olt: "O",
    ont: "N",
    splice_enclosure: "X",
    slack_loop: "L",
    patch_panel: "A",
    conduit: "D"
  };
  return symbols[type] || "F";
}

export function FiberMap({ token }: { token: string }) {
  const [data, setData] = useState<MapResponse | null>(null);
  const [selected, setSelected] = useState<PointFeature | LineFeature | null>(null);
  const [showAssets, setShowAssets] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");
  const dragging = useRef<{ x: number; y: number } | null>(null);

  const load = async () => {
    setWorking(true);
    setError("");

    try {
      setData(await request<MapResponse>("/fiber-map", token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load fiber map");
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    load();
  }, [token]);

  const assets = useMemo(
    () =>
      (data?.assets.features || []).filter(
        (asset) => !statusFilter || asset.properties.status === statusFilter
      ),
    [data, statusFilter]
  );

  const routes = useMemo(
    () =>
      (data?.routes.features || []).filter(
        (route) => !statusFilter || route.properties.status === statusFilter
      ),
    [data, statusFilter]
  );

  const bounds = useMemo(() => calculateBounds(assets, routes), [assets, routes]);

  const project = ([longitude, latitude]: [number, number]) => {
    const width = 1000;
    const height = 620;
    const lonRange = Math.max(bounds.maxLon - bounds.minLon, 0.0001);
    const latRange = Math.max(bounds.maxLat - bounds.minLat, 0.0001);

    return {
      x: ((longitude - bounds.minLon) / lonRange) * width,
      y: height - ((latitude - bounds.minLat) / latRange) * height
    };
  };

  const resetView = () => {
    setZoom(1);
    setPanX(0);
    setPanY(0);
  };

  return (
    <section className="fiber-map-center">
      <div className="fiber-map-header">
        <div>
          <p className="eyebrow">FIBER GIS</p>
          <h2>Interactive Outside Plant Map</h2>
          <p>Mapped fiber assets and route geometry without a third-party map key.</p>
        </div>
        <div className="fiber-map-actions">
          <button onClick={load}>{working ? "Refreshing…" : "Refresh"}</button>
          <button onClick={resetView}>Reset view</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="fiber-map-metrics">
        <article><span>Mapped assets</span><strong>{data?.summary.mapped_assets ?? 0}</strong></article>
        <article><span>Missing coordinates</span><strong>{data?.summary.unmapped_assets ?? 0}</strong></article>
        <article><span>Mapped routes</span><strong>{data?.summary.mapped_routes ?? 0}</strong></article>
        <article><span>Missing geometry</span><strong>{data?.summary.unmapped_routes ?? 0}</strong></article>
      </div>

      <div className="fiber-map-toolbar">
        <label>
          <input type="checkbox" checked={showAssets} onChange={(event) => setShowAssets(event.target.checked)} />
          Assets
        </label>
        <label>
          <input type="checkbox" checked={showRoutes} onChange={(event) => setShowRoutes(event.target.checked)} />
          Routes
        </label>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="planned">Planned</option>
          <option value="construction">Construction</option>
          <option value="warning">Warning</option>
          <option value="damaged">Damaged</option>
          <option value="offline">Offline</option>
          <option value="retired">Retired</option>
        </select>
        <button onClick={() => setZoom((value) => Math.min(value * 1.25, 8))}>Zoom in</button>
        <button onClick={() => setZoom((value) => Math.max(value / 1.25, 0.5))}>Zoom out</button>
      </div>

      <div className="fiber-map-layout">
        <div
          className="fiber-map-canvas"
          onPointerDown={(event) => {
            dragging.current = { x: event.clientX - panX, y: event.clientY - panY };
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (!dragging.current) return;
            setPanX(event.clientX - dragging.current.x);
            setPanY(event.clientY - dragging.current.y);
          }}
          onPointerUp={() => {
            dragging.current = null;
          }}
          onWheel={(event) => {
            event.preventDefault();
            setZoom((value) =>
              Math.min(Math.max(value * (event.deltaY > 0 ? 0.9 : 1.1), 0.5), 8)
            );
          }}
        >
          <svg viewBox="0 0 1000 620" role="img" aria-label="Fiber asset and route map">
            <defs>
              <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
                <path d="M 50 0 L 0 0 0 50" className="fiber-map-grid-line" />
              </pattern>
            </defs>
            <rect width="1000" height="620" className="fiber-map-background" />
            <rect width="1000" height="620" fill="url(#grid)" />

            <g transform={`translate(${panX} ${panY}) scale(${zoom})`}>
              {showRoutes &&
                routes.map((route) => {
                  const points = route.geometry.coordinates
                    .map((coordinate) => {
                      const point = project(coordinate);
                      return `${point.x},${point.y}`;
                    })
                    .join(" ");

                  return (
                    <polyline
                      key={route.id}
                      points={points}
                      className={`fiber-map-route ${route.properties.status}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelected(route);
                      }}
                    />
                  );
                })}

              {showAssets &&
                assets.map((asset) => {
                  const point = project(asset.geometry.coordinates);
                  return (
                    <g
                      key={asset.id}
                      className={`fiber-map-marker ${asset.properties.status}`}
                      transform={`translate(${point.x} ${point.y})`}
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelected(asset);
                      }}
                    >
                      <circle r="11" />
                      <text textAnchor="middle" dominantBaseline="central">
                        {assetSymbol(asset.properties.asset_type)}
                      </text>
                    </g>
                  );
                })}
            </g>
          </svg>

          {!working && !assets.length && !routes.length && (
            <div className="fiber-map-empty">
              No mapped assets or route geometry are available yet.
            </div>
          )}
        </div>

        <aside className="fiber-map-detail">
          {selected ? (
            "asset_type" in selected.properties ? (
              <>
                <p className="eyebrow">FIBER ASSET</p>
                <h3>{selected.properties.name}</h3>
                <dl>
                  <div><dt>Code</dt><dd>{selected.properties.asset_code}</dd></div>
                  <div><dt>Type</dt><dd>{selected.properties.asset_type.replaceAll("_", " ")}</dd></div>
                  <div><dt>Status</dt><dd>{selected.properties.status}</dd></div>
                  <div><dt>Location</dt><dd>{selected.properties.location_name || "Unavailable"}</dd></div>
                  <div><dt>Equipment</dt><dd>{[selected.properties.manufacturer, selected.properties.model].filter(Boolean).join(" ") || "—"}</dd></div>
                  <div><dt>Serial</dt><dd>{selected.properties.serial_number || "—"}</dd></div>
                  <div><dt>Capacity</dt><dd>{selected.properties.used_capacity} / {selected.properties.total_capacity}</dd></div>
                  <div><dt>Coordinates</dt><dd>{(selected.geometry.coordinates as [number, number])[1].toFixed(6)}, {(selected.geometry.coordinates as [number, number])[0].toFixed(6)}</dd></div>
                </dl>
              </>
            ) : (
              <>
                <p className="eyebrow">FIBER ROUTE</p>
                <h3>{selected.properties.name}</h3>
                <dl>
                  <div><dt>Code</dt><dd>{selected.properties.route_code}</dd></div>
                  <div><dt>Status</dt><dd>{selected.properties.status}</dd></div>
                  <div><dt>Cable</dt><dd>{selected.properties.cable_type || "—"}</dd></div>
                  <div><dt>Strands</dt><dd>{selected.properties.strand_count}</dd></div>
                  <div><dt>Length</dt><dd>{selected.properties.length_feet.toLocaleString()} ft</dd></div>
                  <div><dt>Start</dt><dd>{selected.properties.start_location || "—"}</dd></div>
                  <div><dt>End</dt><dd>{selected.properties.end_location || "—"}</dd></div>
                </dl>
              </>
            )
          ) : (
            <>
              <p className="eyebrow">MAP DETAILS</p>
              <h3>Select an asset or route</h3>
              <p>Click a marker or fiber path to inspect its operational details.</p>
            </>
          )}
        </aside>
      </div>

      {!!data?.routes_without_geometry.length && (
        <section className="fiber-map-unmapped">
          <div>
            <p className="eyebrow">GEOMETRY REQUIRED</p>
            <h3>Routes awaiting map geometry</h3>
          </div>
          <div>
            {data.routes_without_geometry.map((route) => (
              <span key={route.id}>{route.route_code} · {route.name}</span>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
