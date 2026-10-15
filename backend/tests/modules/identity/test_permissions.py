import pytest
from fastapi import HTTPException

from app.models import User
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import (
    PERMISSIONS,
    Permission,
    effective_role,
    has_permission,
)
from app.modules.identity.roles import Role

P = Permission

GRANTED: dict[Role, set[Permission]] = {
    Role.MANAGER: {
        P.CATALOG_MANAGE,
        P.INVENTORY_ADJUST,
        P.INVENTORY_REVERSE,
        P.PURCHASING_MANAGE,
        P.ORDERING_CREATE,
        P.ORDERING_VIEW_ALL,
        P.ORDERING_DISCOUNT,
        P.ORDERING_CANCEL,
        P.PAYMENTS_RECORD,
        P.RECIPES_MANAGE,
        P.EXPENSES_MANAGE,
        P.REPORTS_SALES,
    },
    Role.CASHIER: {
        P.ORDERING_CREATE,
        P.ORDERING_VIEW_OWN,
        P.ORDERING_CANCEL,
        P.PAYMENTS_RECORD,
        P.CATALOG_VIEW,
    },
    Role.INVENTORY_STAFF: {
        P.INVENTORY_VIEW,
        P.INVENTORY_MANAGE,
        P.INVENTORY_ADJUST,
        P.PURCHASING_MANAGE,
        P.REPORTS_INVENTORY,
    },
    Role.ACCOUNTANT: {
        P.INVENTORY_VIEW,
        P.ORDERING_VIEW_ALL,
        P.PAYMENTS_READ,
        P.PURCHASING_READ,
        P.REPORTS_SALES,
        P.REPORTS_INVENTORY,
        P.REPORTS_FINANCIAL,
        P.EXPENSES_MANAGE,
        P.SUPPLIER_PAYMENTS_RECORD,
    },
}

DENIED: dict[Role, set[Permission]] = {
    Role.MANAGER: {
        P.USERS_MANAGE,
        P.SETTINGS_MANAGE,
        P.AUDIT_READ,
        P.REPORTS_FINANCIAL,
        P.SUPPLIER_PAYMENTS_RECORD,
    },
    Role.CASHIER: {
        P.CATALOG_MANAGE,
        P.INVENTORY_VIEW,
        P.INVENTORY_ADJUST,
        P.ORDERING_VIEW_ALL,
        P.ORDERING_DISCOUNT,
        P.PAYMENTS_REFUND,
        P.EXPENSES_MANAGE,
        P.REPORTS_SALES,
        P.USERS_MANAGE,
    },
    Role.INVENTORY_STAFF: {
        P.INVENTORY_REVERSE,
        P.ORDERING_CREATE,
        P.PAYMENTS_RECORD,
        P.EXPENSES_READ,
        P.REPORTS_FINANCIAL,
        P.USERS_MANAGE,
    },
    Role.ACCOUNTANT: {
        P.INVENTORY_MANAGE,
        P.ORDERING_CREATE,
        P.PAYMENTS_RECORD,
        P.PURCHASING_MANAGE,
        P.INVENTORY_ADJUST,
        P.USERS_MANAGE,
        P.SETTINGS_MANAGE,
    },
}


def _user(role: Role, *, is_superuser: bool = False) -> User:
    return User(
        email="someone@example.com",
        hashed_password="x",
        role=role,
        is_superuser=is_superuser,
    )


def test_every_role_has_a_permission_set() -> None:
    assert set(PERMISSIONS) == set(Role)


def test_owner_has_every_permission() -> None:
    owner = _user(Role.OWNER)
    assert all(has_permission(owner, permission) for permission in Permission)


@pytest.mark.parametrize("role", list(GRANTED))
def test_role_grants(role: Role) -> None:
    user = _user(role)
    for permission in GRANTED[role]:
        assert has_permission(user, permission), f"{role} should have {permission}"


@pytest.mark.parametrize("role", list(DENIED))
def test_role_denials(role: Role) -> None:
    user = _user(role)
    for permission in DENIED[role]:
        assert not has_permission(user, permission), (
            f"{role} must not have {permission}"
        )


def test_superuser_is_treated_as_owner() -> None:
    user = _user(Role.CASHIER, is_superuser=True)
    assert effective_role(user) == Role.OWNER
    assert has_permission(user, P.USERS_MANAGE)


def test_require_permission_returns_user_when_allowed() -> None:
    user = _user(Role.INVENTORY_STAFF)
    assert require_permission(P.INVENTORY_ADJUST)(user) is user


def test_require_permission_denies_with_403() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_permission(P.INVENTORY_ADJUST)(_user(Role.CASHIER))
    assert exc_info.value.status_code == 403
