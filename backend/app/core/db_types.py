from enum import Enum
from typing import Any

from sqlalchemy import Dialect, String
from sqlalchemy.types import TypeDecorator


class EnumString(TypeDecorator[Any]):
    """Stores a `str`-valued Enum as its value in a VARCHAR column.

    Pair it with a `CheckConstraint` listing the allowed values; a native
    PostgreSQL enum is avoided so adding values needs no type migration.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[Enum], length: int = 32) -> None:
        super().__init__(length=length)
        self.enum_class = enum_class

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        return self.enum_class(value).value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        return self.enum_class(value)
