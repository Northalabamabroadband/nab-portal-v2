# MikroTik RouterOS integration

RC1 Build 025 adds read-only MikroTik RouterOS v7 telemetry to NAB Mission
Control for internal network infrastructure. It covers core, tower, POP, and
backhaul-edge routers. The portal reads router identity and resources,
interfaces, IP addresses, routes, DHCP leases, and ARP entries through the
RouterOS REST API. DHCP and ARP records are normalized into one infrastructure
neighbor view.

This integration is not part of Customer 360, Managed Wi-Fi, the subscriber
portal, or customer-device assignment. Access requires the internal
`network.read` permission.

## RouterOS preparation

Use RouterOS v7 with the HTTPS service enabled. Create a dedicated account and
restrict its source address to the NAB Portal API host or subnet. Run these
commands in a RouterOS terminal after replacing every angle-bracket placeholder:

```routeros
/user/group/add name=nab-portal policy=read,rest-api
/user/add name=nab-portal group=nab-portal password="<STRONG_UNIQUE_PASSWORD>" address=<PORTAL_API_IP>/32
/ip/service/enable www-ssl
/ip/service/set www-ssl address=<PORTAL_API_IP>/32 certificate=<ROUTER_CERTIFICATE_NAME>
```

Keep WinBox or a local administrative session open while applying access
restrictions so a typo does not lock out router management. The portal account
does not need write, policy, sensitive, reboot, or local-login privileges.

## Portal configuration

Add these values only to the private `.env` file on the deployed server:

```dotenv
MIKROTIK_BASE_URL=https://<ROUTER_ADDRESS>/rest
MIKROTIK_USERNAME=nab-portal
MIKROTIK_PASSWORD=<STRONG_UNIQUE_PASSWORD>
MIKROTIK_VERIFY_TLS=true
MIKROTIK_CA_CERT=
MIKROTIK_TIMEOUT_SECONDS=15
```

Do not commit the deployed `.env` file. When the router certificate is issued by
a private CA, place only the CA certificate at `secrets/mikrotik/ca.crt` and set:

```dotenv
MIKROTIK_CA_CERT=/run/secrets/mikrotik/ca.crt
```

The API container mounts `secrets/mikrotik` read-only. Do not put the router
password or a private key in that directory.

## Verification

After deployment, sign in to Mission Control and open **RouterOS**. The page
should show Connected, the router identity, interface state, routes, DHCP leases,
and observed infrastructure neighbors. **Systems Check** also reports the MikroTik probe.

Build 025 intentionally has no router mutation endpoints. Configuration changes,
reboots, firewall operations, and package updates remain RouterOS-only.

## Live interface throughput

RC1 Build 026 adds a read-only `GET /api/v2/mikrotik/throughput`
counter-sampling endpoint and two live charts at the bottom of **MikroTik NOC**.
Operators select up to six interfaces in the existing interface table. The
browser polls every three seconds, derives bits per second from RouterOS RX/TX
byte-counter deltas, handles counter resets without showing negative traffic,
and retains a bounded six-minute rolling window.

The two charts show receive and transmit throughput separately. Sampling pauses
while the browser tab is hidden and resumes with a fresh baseline. No RouterOS
configuration command is executed, no persistent telemetry duplicate is
created, and the endpoint remains protected by the existing internal
`network.read` permission.
