from app.models import UserPublic
from app.modules.identity.permissions import Permission
from app.modules.identity.roles import Role


class UserMePublic(UserPublic):
    role: Role
    permissions: list[Permission]
