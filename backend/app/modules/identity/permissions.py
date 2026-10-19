from enum import Enum

from app.models import User
from app.modules.identity.roles import Role


class Permission(str, Enum):
    USERS_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"
    AUDIT_READ = "audit:read"

    CATALOG_VIEW = "catalog:view"
    CATALOG_MANAGE = "catalog:manage"

    INVENTORY_VIEW = "inventory:view"
    INVENTORY_MANAGE = "inventory:manage"
    INVENTORY_ADJUST = "inventory:adjust"
    INVENTORY_REVERSE = "inventory:reverse"
    INVENTORY_RETURN = "inventory:return"

    PURCHASING_READ = "purchasing:read"
    PURCHASING_MANAGE = "purchasing:manage"
    PURCHASING_POST = "purchasing:post"
    PURCHASING_REVERSE = "purchasing:reverse"

    RECIPES_READ = "recipes:read"
    RECIPES_MANAGE = "recipes:manage"

    PRODUCTION_VIEW = "production:view"
    PRODUCTION_MANAGE = "production:manage"
    PRODUCTION_COMPLETE = "production:complete"
    PRODUCTION_BACKDATE = "production:backdate"
    PRODUCTION_REVERSE = "production:reverse"
    PRODUCTION_TRACEABILITY = "production:traceability"

    ORDERING_CREATE = "ordering:create"
    ORDERING_VIEW_OWN = "ordering:view_own"
    ORDERING_VIEW_ALL = "ordering:view_all"
    ORDERING_DISCOUNT = "ordering:discount"
    ORDERING_CANCEL = "ordering:cancel"

    PAYMENTS_READ = "payments:read"
    PAYMENTS_RECORD = "payments:record"
    PAYMENTS_VOID = "payments:void"
    PAYMENTS_REFUND = "payments:refund"
    PAYMENTS_CONFIGURE = "payments:configure"

    EXPENSES_READ = "expenses:read"
    EXPENSES_MANAGE = "expenses:manage"

    SUPPLIER_PAYMENTS_READ = "supplier_payments:read"
    SUPPLIER_PAYMENTS_RECORD = "supplier_payments:record"

    CASH_VIEW = "cash:view"
    CASH_ADJUST = "cash:adjust"
    FINANCE_VIEW = "finance:view"

    REPORTS_SALES = "reports:sales"
    REPORTS_INVENTORY = "reports:inventory"
    REPORTS_FINANCIAL = "reports:financial"


P = Permission

PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.MANAGER: frozenset(
        {
            P.CATALOG_VIEW,
            P.CATALOG_MANAGE,
            P.INVENTORY_VIEW,
            P.INVENTORY_MANAGE,
            P.INVENTORY_ADJUST,
            P.INVENTORY_REVERSE,
            P.INVENTORY_RETURN,
            P.PURCHASING_READ,
            P.PURCHASING_MANAGE,
            P.PURCHASING_POST,
            P.PURCHASING_REVERSE,
            P.RECIPES_READ,
            P.RECIPES_MANAGE,
            P.PRODUCTION_VIEW,
            P.PRODUCTION_MANAGE,
            P.PRODUCTION_COMPLETE,
            P.PRODUCTION_BACKDATE,
            P.PRODUCTION_REVERSE,
            P.PRODUCTION_TRACEABILITY,
            P.ORDERING_CREATE,
            P.ORDERING_VIEW_OWN,
            P.ORDERING_VIEW_ALL,
            P.ORDERING_DISCOUNT,
            P.ORDERING_CANCEL,
            P.PAYMENTS_READ,
            P.PAYMENTS_RECORD,
            P.PAYMENTS_VOID,
            P.PAYMENTS_REFUND,
            P.EXPENSES_READ,
            P.EXPENSES_MANAGE,
            P.CASH_VIEW,
            P.REPORTS_SALES,
        }
    ),
    Role.CASHIER: frozenset(
        {
            P.CATALOG_VIEW,
            P.ORDERING_CREATE,
            P.ORDERING_VIEW_OWN,
            P.ORDERING_CANCEL,
            P.PAYMENTS_READ,
            P.PAYMENTS_RECORD,
        }
    ),
    Role.INVENTORY_STAFF: frozenset(
        {
            P.CATALOG_VIEW,
            P.INVENTORY_VIEW,
            P.INVENTORY_MANAGE,
            P.INVENTORY_ADJUST,
            P.PRODUCTION_VIEW,
            P.PRODUCTION_MANAGE,
            P.PRODUCTION_COMPLETE,
            P.PRODUCTION_TRACEABILITY,
            P.PURCHASING_READ,
            P.PURCHASING_MANAGE,
            P.PURCHASING_POST,
            P.REPORTS_INVENTORY,
        }
    ),
    Role.ACCOUNTANT: frozenset(
        {
            P.CATALOG_VIEW,
            P.INVENTORY_VIEW,
            P.ORDERING_VIEW_ALL,
            P.PAYMENTS_READ,
            P.PURCHASING_READ,
            P.EXPENSES_READ,
            P.EXPENSES_MANAGE,
            P.SUPPLIER_PAYMENTS_READ,
            P.SUPPLIER_PAYMENTS_RECORD,
            P.CASH_VIEW,
            P.FINANCE_VIEW,
            P.REPORTS_SALES,
            P.REPORTS_INVENTORY,
            P.REPORTS_FINANCIAL,
        }
    ),
}


def effective_role(user: User) -> Role:
    if user.is_superuser:
        return Role.OWNER
    return Role(user.role)


def permissions_for(user: User) -> frozenset[Permission]:
    return PERMISSIONS[effective_role(user)]


def has_permission(user: User, permission: Permission) -> bool:
    return permission in permissions_for(user)
