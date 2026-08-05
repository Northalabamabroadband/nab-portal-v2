import React, { useEffect, useMemo, useState } from "react";
import { request } from "./api";

type User = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_superuser: boolean;
  roles: string[];
};

type Role = {
  id: string;
  name: string;
  description: string;
  permissions: string[];
};

type Permission = { code: string; description: string };
export type AccessInventory = { users?: User[]; roles?: Role[]; permissions?: Permission[] };

export function AccessControl({
  token,
  access,
  onChanged
}: {
  token: string;
  access?: AccessInventory | null;
  onChanged: () => Promise<void>;
}) {
  const inventory = useMemo(() => ({
    users: Array.isArray(access?.users) ? access.users : [],
    roles: Array.isArray(access?.roles) ? access.roles : [],
    permissions: Array.isArray(access?.permissions) ? access.permissions : []
  }), [access]);
  const complete = Boolean(access) && Array.isArray(access?.users) && Array.isArray(access?.roles) && Array.isArray(access?.permissions);
  const [userRoles, setUserRoles] = useState<Record<string, string[]>>({});
  const [rolePermissions, setRolePermissions] = useState<Record<string, string[]>>({});
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setUserRoles(Object.fromEntries(inventory.users.map(user => [user.id, Array.isArray(user.roles) ? user.roles : []])));
    setRolePermissions(Object.fromEntries(inventory.roles.map(role => [role.id, Array.isArray(role.permissions) ? role.permissions : []])));
  }, [inventory]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setWorking(label); setError(""); setMessage("");
    try {
      await action();
      await onChanged();
      setMessage("Access changes saved and are now active.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update access");
    } finally {
      setWorking("");
    }
  };

  const toggle = (values: string[], value: string) =>
    values.includes(value) ? values.filter(item => item !== value) : [...values, value].sort();

  if (!complete) {
    return <article className="feature-recovery" role="status">
      <p className="eyebrow">ACCESS DATA</p>
      <h3>Access controls are temporarily unavailable</h3>
      <p>The administration service returned an incomplete response. Refresh to try again; no account settings were changed.</p>
      <button type="button" onClick={onChanged}>Reload access controls</button>
    </article>;
  }

  return <div className="access-control">
    {error && <div className="error-message">{error}</div>}
    {message && <div className="dispatch-message">{message}</div>}

    <section>
      <div className="panel-heading"><div><p className="eyebrow">ADMINISTRATORS</p><h3>User access</h3></div></div>
      {inventory.users.length === 0
        ? <p className="access-empty">No administrator accounts were returned.</p>
        : <div className="access-grid">{inventory.users.map(user => <article key={user.id}>
          <div className="access-title"><div><strong>{user.display_name || "Unnamed administrator"}</strong><small>{user.email || "No email address"}</small></div><span className={user.is_active ? "access-active" : "access-inactive"}>{user.is_active ? "Active" : "Disabled"}</span></div>
          <div className="access-options">{inventory.roles.map(role => <label key={role.id}><input type="checkbox" checked={(userRoles[user.id] || []).includes(role.name)} onChange={() => setUserRoles(current => ({ ...current, [user.id]: toggle(current[user.id] || [], role.name) }))} /><span>{role.name.replaceAll("_", " ")}</span></label>)}</div>
          <div className="access-actions">
            <button disabled={Boolean(working)} onClick={() => run(user.id, () => request(`/admin/users/${user.id}`, token, { method: "PATCH", body: JSON.stringify({ role_names: userRoles[user.id] || [] }) }))}>Save roles</button>
            <button className={user.is_active ? "danger-action" : ""} disabled={Boolean(working)} onClick={() => run(user.id, () => request(`/admin/users/${user.id}`, token, { method: "PATCH", body: JSON.stringify({ is_active: !user.is_active }) }))}>{user.is_active ? "Disable" : "Enable"}</button>
          </div>
          {user.is_superuser && <small className="guard-note">Protected superuser account</small>}
        </article>)}</div>}
    </section>

    <section>
      <div className="panel-heading"><div><p className="eyebrow">ROLE POLICY</p><h3>Role permissions</h3></div></div>
      {inventory.roles.length === 0
        ? <p className="access-empty">No role policies were returned.</p>
        : <div className="access-grid">{inventory.roles.map(role => <article key={role.id}>
          <div className="access-title"><div><strong>{role.name.replaceAll("_", " ")}</strong><small>{role.description}</small></div><span>{(rolePermissions[role.id] || []).length} permissions</span></div>
          <div className="permission-options">{inventory.permissions.map(permission => <label key={permission.code} title={permission.description}><input type="checkbox" checked={(rolePermissions[role.id] || []).includes(permission.code)} onChange={() => setRolePermissions(current => ({ ...current, [role.id]: toggle(current[role.id] || [], permission.code) }))} /><span>{permission.code}</span></label>)}</div>
          <button disabled={Boolean(working)} onClick={() => run(role.id, () => request(`/admin/roles/${role.id}`, token, { method: "PATCH", body: JSON.stringify({ permission_codes: rolePermissions[role.id] || [] }) }))}>Save permission policy</button>
          {role.name === "super_admin" && <small className="guard-note">admin.manage is protected</small>}
        </article>)}</div>}
    </section>
  </div>;
}
