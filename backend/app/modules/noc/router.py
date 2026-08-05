from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(prefix="/noc", tags=["noc"])


@router.get("/summary")
def noc_summary() -> dict[str, object]:
    return {
        "status": "operational",
        "network_health": "foundation",
        "active_outages": 0,
        "sites_online": 0,
        "customers_affected": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
