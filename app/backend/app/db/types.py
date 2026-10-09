"""Column types shared by the ORM models."""

from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import Enum, TypeDecorator
from sqlalchemy.dialects import mysql

# Unsigned integers (money is whole AMD, ids are unsigned).
UInt = mysql.INTEGER(unsigned=True)
UBigInt = mysql.BIGINT(unsigned=True)
USmallInt = mysql.SMALLINT(unsigned=True)


class UtcDateTime(TypeDecorator[datetime]):
    """DATETIME(6) holding UTC. Python side is always timezone-aware UTC.

    The application writes the value (from Clock); MySQL never converts it.
    """

    impl = mysql.DATETIME(fsp=6)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime is not allowed; use timezone-aware UTC")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class AsciiBinEnum(Enum):
    """Non-native enum stored as VARCHAR ... CHARACTER SET ascii COLLATE ascii_bin.

    The binary collation makes the CHECK constraint case-sensitive ('new' is rejected).
    SQLAlchemy's Enum drops `collation=` and has no charset, so both are set here.
    """

    inherit_cache = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.charset = "ascii"
        self.collation = "ascii_bin"


def str_enum(enum_cls: type[PyEnum], *, name: str, length: int) -> Enum:
    """VARCHAR + named CHECK instead of a native ENUM (memory/06-decisions.md, B4)."""
    return AsciiBinEnum(
        enum_cls,
        name=name,
        length=length,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


# Pickup code column: ASCII, binary collation (case-sensitive REGEXP in ck_orders_code).
CodeChar = mysql.CHAR(5, charset="ascii", collation="ascii_bin")
