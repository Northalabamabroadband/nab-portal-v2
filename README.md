# North Alabama Broadband Portal v2

Milestone 1 foundation for the new NAB Portal v2 codebase.

Included:

- FastAPI application shell
- PostgreSQL-ready SQLAlchemy configuration
- Redis-ready configuration
- modular service layout
- health and readiness endpoints
- initial NOC summary endpoint
- environment template
- Docker Compose development stack
- migration-ready project structure
- test scaffolding
- production deployment notes

This release is intentionally separate from `/opt/nab-portal`. It does not modify the current production portal.

## Start

```bash
cp .env.example .env
docker compose up -d --build
curl http://127.0.0.1:8200/health
```

## Default ports

- API: `8200`
- PostgreSQL: internal only
- Redis: internal only
