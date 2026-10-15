from collections.abc import Callable

from fastapi import HTTPException

from app.api.deps import CurrentUser
from app.models import User
from app.modules.identity.permissions import Permission, has_permission

INSUFFICIENT_PRIVILEGES = "The user doesn't have enough privileges"


def require_permission(permission: Permission) -> Callable[[User], User]:
    """FastAPI dependency: the current active user, or 403 without `permission`."""

    def dependency(current_user: CurrentUser) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(status_code=403, detail=INSUFFICIENT_PRIVILEGES)
        return current_user

    return dependency
