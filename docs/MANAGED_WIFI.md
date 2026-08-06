# Managed Wi‑Fi Operations

RC1 Build 028 replaces the Managed Wi‑Fi placeholder with an operational TAUC
workspace. It reuses the customer gateway assignments already maintained in
Customer 360; there is no second inventory or customer-device mapping.

## Included operations

- Search and select every durable customer gateway assignment.
- Read the selected gateway, SSIDs/radios, and connected devices.
- Inspect client name, IP, MAC, band, and signal quality.
- Run portal diagnostics with the assignment's saved network identity.
- Run the optional provider diagnostic endpoint when configured.
- Change SSID and Wi‑Fi password when the verified tenant paths are configured.
- Reboot a gateway only after the operator types `REBOOT`.

TAUC requests continue through the shared one-at-a-time throttle, global
rate-limit cooldown, in-flight request coalescing, and short snapshot cache.
Successful write controls invalidate that gateway's cached snapshot.

## Write endpoint activation

Keep these values only in the deployed `.env` file:

```dotenv
TAUC_WIFI_SSID_UPDATE_PATH=
TAUC_WIFI_PASSWORD_UPDATE_PATH=
TAUC_REBOOT_PATH=
TAUC_DIAGNOSTICS_PATH=
```

Paths may contain `{device_id}` / `{deviceId}` or `{network_id}` /
`{networkId}` according to the tenant contract. Leave an unverified endpoint
blank; the corresponding control remains visibly disabled.

Wi‑Fi passwords are accepted only as 8–63 character passphrases or 64
hexadecimal characters. Passwords and TAUC credentials are never returned by
the API, written to PostgreSQL, or committed to Git.
