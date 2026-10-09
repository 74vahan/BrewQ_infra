from sqlalchemy.orm import DeclarativeBase

# Table-level options shared by all tables (memory/02-database.md, "Common conventions").
TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class Base(DeclarativeBase):
    pass
