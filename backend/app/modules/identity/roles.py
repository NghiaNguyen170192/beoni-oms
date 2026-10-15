from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    MANAGER = "manager"
    CASHIER = "cashier"
    INVENTORY_STAFF = "inventory_staff"
    ACCOUNTANT = "accountant"


ROLE_VALUES_SQL = ", ".join(f"'{role.value}'" for role in Role)
