# NAB Command desktop synchronization

The desktop synchronization API is available under `/api/desktop/v1` and is
separate from browser session authentication. Every route requires the
`X-NAB-API-Key` header.

Set a unique value only in the deployed server `.env` file:

```dotenv
NAB_DESKTOP_API_KEY=<LONG_RANDOM_VALUE>
```

Do not commit the deployed value. The repository template intentionally leaves
the value blank, which causes the API to fail closed with HTTP 503.

Endpoints:

- `GET /api/desktop/v1/health`
- `GET /api/desktop/v1/snapshot`
- `POST /api/desktop/v1/work-orders`
- `POST /api/desktop/v1/outages`
- `PATCH /api/desktop/v1/outages/{outage_id}`

Work orders use the existing portal work-order table. Desktop-originated
outages use the persistent `desktop_outages_v2` PostgreSQL table so records
survive API restarts. Reusing an outage `external_key` updates the existing
record rather than creating a duplicate.
