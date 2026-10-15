from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import crud
from app.models import User, UserCreate, UserUpdate
from app.modules.audit import service as audit
from app.modules.identity.permissions import effective_role, permissions_for
from app.modules.identity.schemas import UserMePublic

_ROLE_FIELDS = ("role", "is_superuser")
_ACTIVATION_FIELDS = ("is_active",)


class UserHasHistory(Exception):
    """The user is referenced by audit history and cannot be deleted."""


class CannotChangeOwnRole(Exception):
    pass


def _access_snapshot(user: User) -> dict[str, Any]:
    return {
        "role": user.role,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
    }


def me(user: User) -> UserMePublic:
    return UserMePublic.model_validate(
        user,
        update={
            "role": effective_role(user),
            "permissions": sorted(permissions_for(user), key=lambda p: p.value),
        },
    )


def create_user(session: Session, *, user_in: UserCreate, actor: User) -> User:
    user = crud.build_user(user_in)
    session.add(user)
    session.flush()
    audit.record(
        session,
        actor=actor,
        entity_type="user",
        entity_id=user.id,
        action="created",
        changes=audit.diff({}, _access_snapshot(user), _access_snapshot(user)),
    )
    session.commit()
    session.refresh(user)
    return user


def update_user(
    session: Session, *, user: User, user_in: UserUpdate, actor: User
) -> User:
    old = _access_snapshot(user)
    crud.apply_user_update(user, user_in)
    new = _access_snapshot(user)

    role_changes = audit.diff(old, new, _ROLE_FIELDS)
    activation_changes = audit.diff(old, new, _ACTIVATION_FIELDS)
    if role_changes and user.id == actor.id:
        session.rollback()
        raise CannotChangeOwnRole()

    session.add(user)
    if role_changes:
        audit.record(
            session,
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            action="role_changed",
            changes=role_changes,
        )
    if activation_changes:
        audit.record(
            session,
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            action="activated" if user.is_active else "deactivated",
            changes=activation_changes,
        )
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, *, user: User, actor: User) -> None:
    user_id = user.id
    session.delete(user)
    audit.record(
        session,
        actor=None if actor.id == user_id else actor,
        entity_type="user",
        entity_id=user_id,
        action="deleted",
        changes=audit.diff(_access_snapshot(user), {}, _access_snapshot(user)),
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise UserHasHistory()
