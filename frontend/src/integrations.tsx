import React, { useEffect, useState } from "react";

type ServiceStatus = {
  configured: boolean;
  connected?: boolean | null;
  base_url?: string;
  auth_mode?: string;
  authentication_mode?: string;
  path?: string;
  record_count?: number;
  detail?: string;
  errors?: string[];
  certificate_present?: boolean;
  private_key_present?: boolean;
  access_key_configured?: boolean;
  secret_key_configured?: boolean;
  test_device?: Record<string, unknown>;
  test_network?: Record<string, unknown>;
};

type HealthResponse = {
  uisp_crm: ServiceStatus;
  uisp_nms: ServiceStatus;
  tauc: ServiceStatus;
  configuration: Record<string, unknown>;
};

async function request<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`/api/v2${path}`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`
    },
    credentials: "include"
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function ServiceCard({
  title,
  status
}: {
  title: string;
  status: ServiceStatus;
}) {
  const state =
    status.connected === true
      ? "connected"
      : status.connected === false
      ? "failed"
      : status.configured
      ? "configured"
      : "missing";

  return (
    <article className={`integration-card ${state}`}>
      <div>
        <div>
          <p className="eyebrow">{title}</p>
          <h3>{state.replaceAll("_", " ")}</h3>
        </div>
        <span>{state}</span>
      </div>

      <dl>
        <div><dt>Configured</dt><dd>{status.configured ? "Yes" : "No"}</dd></div>
        {status.base_url && <div><dt>Base URL</dt><dd>{status.base_url}</dd></div>}
        {(status.auth_mode || status.authentication_mode) && (
          <div><dt>Authentication</dt><dd>{status.auth_mode || status.authentication_mode}</dd></div>
        )}
        {status.path && <div><dt>Working path</dt><dd>{status.path}</dd></div>}
        {status.record_count !== undefined && (
          <div><dt>Records visible</dt><dd>{status.record_count}</dd></div>
        )}
        {status.certificate_present !== undefined && (
          <div><dt>Certificate</dt><dd>{status.certificate_present ? "Present" : "Missing"}</dd></div>
        )}
        {status.private_key_present !== undefined && (
          <div><dt>Private key</dt><dd>{status.private_key_present ? "Present" : "Missing"}</dd></div>
        )}
      </dl>

      {status.detail && <p className="integration-detail">{status.detail}</p>}

      {!!status.errors?.length && (
        <details>
          <summary>Probe errors</summary>
          <ul>
            {status.errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </details>
      )}
    </article>
  );
}

export function IntegrationHealth({ token }: { token: string }) {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setWorking(true);
    setError("");

    try {
      setData(await request<HealthResponse>("/integrations/health", token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to test integrations");
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    load();
  }, [token]);

  return (
    <section className="integration-center">
      <div className="integration-header">
        <div>
          <p className="eyebrow">CORE INTEGRATIONS</p>
          <h2>UISP CRM, UISP NMS & TAUC</h2>
          <p>Live configuration and endpoint diagnostics for the portal's core systems.</p>
        </div>
        <button onClick={load}>{working ? "Testing…" : "Run diagnostics"}</button>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="integration-grid">
        {data && (
          <>
            <ServiceCard title="UISP CRM" status={data.uisp_crm} />
            <ServiceCard title="UISP NMS" status={data.uisp_nms} />
            <ServiceCard title="TP-Link TAUC" status={data.tauc} />
          </>
        )}
      </div>

      {data && (
        <article className="integration-config">
          <p className="eyebrow">ACTIVE ENDPOINT CONFIGURATION</p>
          <pre>{JSON.stringify(data.configuration, null, 2)}</pre>
        </article>
      )}
    </section>
  );
}
