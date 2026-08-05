# NAB Portal v2 RC1 Build 001

Consolidated from the uploaded live source snapshot.

- unified production Compose file
- preserved `.env` installer behavior
- UISP CRM/NMS separation and legacy key aliases
- default UISP `X-Auth-App-Key` authentication
- production TAUC mTLS AK/SK `X-Authorization` adapter
- NMS-backed Network Center
- Fiber Map TypeScript coordinate narrowing retained
- clean API router ordering
- install, validation, and rollback scripts

The archive intentionally excludes live `.env` values and certificates.
