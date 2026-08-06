# MikroTik fleet collector

RC1 Build 027 moves interface counter polling out of operator browsers and into
one backend collector. Redis elects one collector leader, stores the live
rolling window, and fans samples out through the existing portal WebSocket.
PostgreSQL stores one-minute interface rollups for longer history.

## Secret router profiles

Create `secrets/mikrotik/routers.json` only on the deployed server. The
directory is already mounted read-only at `/run/secrets/mikrotik` in the API
container. Do not add this file to Git.

```json
{
  "routers": [
    {
      "key": "core-1",
      "name": "Core Router 1",
      "site": "Main Office",
      "role": "core",
      "base_url": "https://router.example.com/rest",
      "username": "nab-portal",
      "password": "REPLACE_ON_SERVER",
      "verify_tls": true,
      "ca_cert": "/run/secrets/mikrotik/ca.crt",
      "poll_interval_seconds": 3,
      "enabled": true
    }
  ]
}
```

Instead of a `password` property, a profile may use `"password_env":
"MIKROTIK_CORE_1_PASSWORD"` and keep that value in the deployed `.env` file.
Profile keys must be unique lowercase identifiers containing only letters,
numbers, `_`, or `-`.

When the routers file is absent, the existing `MIKROTIK_BASE_URL`,
`MIKROTIK_USERNAME`, and `MIKROTIK_PASSWORD` variables continue to provide the
single `default` router profile.

## Data retention

- Redis keeps the most recent `MIKROTIK_HISTORY_POINTS` samples per router.
- PostgreSQL keeps minute rollups for `MIKROTIK_ROLLUP_RETENTION_DAYS`.
- A Redis lease prevents multiple API instances from polling the same fleet.
- Router credentials are loaded only by the backend and are never included in
  fleet API responses or WebSocket events.

All Build 027 MikroTik actions remain read-only and internal to the NOC.
