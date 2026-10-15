from fastapi import APIRouter

from app.api.routes import login, private, users, utils
from app.core.config import settings
from app.modules.accounting import routes as accounting_routes
from app.modules.audit import routes as audit_routes
from app.modules.catalog import routes as catalog_routes
from app.modules.inventory import routes as inventory_routes
from app.modules.ordering import routes as ordering_routes
from app.modules.payments import routes as payments_routes
from app.modules.purchasing import routes as purchasing_routes
from app.modules.recipes import routes as recipes_routes
from app.modules.reporting import routes as reporting_routes
from app.modules.settings import routes as settings_routes

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(settings_routes.router)
api_router.include_router(audit_routes.router)
api_router.include_router(catalog_routes.router)
api_router.include_router(inventory_routes.router)
api_router.include_router(ordering_routes.router)
api_router.include_router(purchasing_routes.router)
api_router.include_router(payments_routes.router)
api_router.include_router(recipes_routes.router)
api_router.include_router(accounting_routes.router)
api_router.include_router(reporting_routes.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
