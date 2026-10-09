"""Initial schema: six tables exactly as in memory/02-database.md.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}

UINT = mysql.INTEGER(unsigned=True)
UBIGINT = mysql.BIGINT(unsigned=True)
USMALLINT = mysql.SMALLINT(unsigned=True)
DT6 = mysql.DATETIME(fsp=6)

# Enum-like columns: ASCII + binary collation, so the CHECKs are case-sensitive.
ASCII_BIN = {"charset": "ascii", "collation": "ascii_bin"}

STATUSES = "'NEW', 'IN_PROGRESS', 'READY', 'PICKED_UP', 'CANCELLED'"


def upgrade() -> None:
    op.create_table(
        "menu_items",
        sa.Column("id", UINT, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", mysql.VARCHAR(16, **ASCII_BIN), nullable=False),
        sa.Column("price_s", UINT, nullable=True),
        sa.Column("price_m", UINT, nullable=False),
        sa.Column("price_l", UINT, nullable=True),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("image_url", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_menu_items_name"),
        sa.CheckConstraint("category IN ('coffee', 'tea', 'cake')", name="ck_menu_items_category"),
        sa.CheckConstraint(
            "price_m > 0 AND (price_s IS NULL OR price_s > 0) AND (price_l IS NULL OR price_l > 0)",
            name="ck_menu_items_prices",
        ),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "customers",
        sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
        sa.Column("device_id", mysql.CHAR(36, charset="ascii"), nullable=False),
        sa.Column("name", sa.String(40), server_default=sa.text("NULL"), nullable=True),
        sa.Column("created_at", DT6, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", name="uq_customers_device_id"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "cart_items",
        sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
        sa.Column("customer_id", UBIGINT, nullable=False),
        sa.Column("menu_item_id", UINT, nullable=False),
        sa.Column("size", mysql.VARCHAR(1, **ASCII_BIN), nullable=False),
        sa.Column("qty", USMALLINT, nullable=False),
        sa.Column("updated_at", DT6, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name="fk_cart_items_customer", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], name="fk_cart_items_menu_item", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("customer_id", "menu_item_id", "size", name="uq_cart_items_line"),
        sa.CheckConstraint("size IN ('S', 'M', 'L')", name="ck_cart_items_size"),
        sa.CheckConstraint("qty BETWEEN 1 AND 20", name="ck_cart_items_qty"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "orders",
        sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
        sa.Column("code", mysql.CHAR(5, **ASCII_BIN), nullable=False),
        sa.Column("customer_id", UBIGINT, nullable=False),
        sa.Column("status", mysql.VARCHAR(16, **ASCII_BIN), server_default="NEW", nullable=False),
        sa.Column("total_amd", UINT, nullable=False),
        sa.Column("created_at", DT6, nullable=False),
        sa.Column("updated_at", DT6, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name="fk_orders_customer", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("code REGEXP '^A-[0-9]{3}$' AND code <> 'A-000'", name="ck_orders_code"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_orders_status"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_orders_customer_created", "orders", ["customer_id", "created_at"])
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])
    # Functional unique index: one code per Yerevan day (UTC+4, no DST). The same
    # expression must be used verbatim by the MAX(code) query (repositories/orders.py).
    op.execute(
        "CREATE UNIQUE INDEX uq_orders_day_code "
        "ON orders ((DATE(created_at + INTERVAL 4 HOUR)), code)"
    )

    op.create_table(
        "order_items",
        sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
        sa.Column("order_id", UBIGINT, nullable=False),
        sa.Column("menu_item_id", UINT, nullable=False),
        sa.Column("size", mysql.VARCHAR(1, **ASCII_BIN), nullable=False),
        sa.Column("qty", USMALLINT, nullable=False),
        sa.Column("unit_price_amd", UINT, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_order_items_order", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            name="fk_order_items_menu_item",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("order_id", "menu_item_id", "size", name="uq_order_items_line"),
        sa.CheckConstraint("size IN ('S', 'M', 'L')", name="ck_order_items_size"),
        sa.CheckConstraint("qty BETWEEN 1 AND 20", name="ck_order_items_qty"),
        sa.CheckConstraint("unit_price_amd > 0", name="ck_order_items_price"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "order_events",
        sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
        sa.Column("order_id", UBIGINT, nullable=False),
        sa.Column("from_status", mysql.VARCHAR(16, **ASCII_BIN), nullable=True),
        sa.Column("to_status", mysql.VARCHAR(16, **ASCII_BIN), nullable=False),
        sa.Column("created_at", DT6, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_order_events_order", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(f"from_status IN ({STATUSES})", name="ck_order_events_from_status"),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name="ck_order_events_to_status"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_order_events_order", "order_events", ["order_id", "created_at"])


def downgrade() -> None:
    # Not used in production (migrations only go forward); needed by tests.
    op.drop_table("order_events")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("cart_items")
    op.drop_table("customers")
    op.drop_table("menu_items")
