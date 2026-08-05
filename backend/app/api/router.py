from app.modules.audit.router import router as audit_router
from app.modules.alerts.router import router as alerts_router
from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.billingcenter.router import router as billingcenter_router
from app.modules.customer360.router import router as customer360_router
from app.modules.customers.router import router as customers_router
from app.modules.customers.tauc_router import router as customer_tauc_router
from app.modules.fiber.router import router as fiber_router
from app.modules.fibermap.router import router as fibermap_router
from app.modules.integrations.router import router as integrations_router
from app.modules.inventory.router import router as inventory_router
from app.modules.live.router import router as live_router
from app.modules.networkcenter.router import router as networkcenter_router
from app.modules.noc.router import router as noc_router
from app.modules.operations.router import router as operations_router
from app.modules.search.router import router as search_router
from app.modules.tauc.router import router as tauc_router
from app.modules.tickets.router import router as tickets_router
from app.modules.uisp.router import router as uisp_router
from app.modules.workorders.router import router as workorders_router

router = APIRouter(prefix="/api/v2")
for child in (auth_router, customers_router, customer_tauc_router, customer360_router, search_router, live_router, noc_router, uisp_router, tauc_router, tickets_router, workorders_router, inventory_router, operations_router, billingcenter_router, networkcenter_router, fiber_router, fibermap_router, integrations_router, alerts_router, audit_router):
    router.include_router(child)
