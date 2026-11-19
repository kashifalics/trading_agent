"""prospective paper shadow experiment outcomes

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-19 14:17:00
"""
import sqlalchemy as sa
from alembic import op

import app.database.types

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TS = app.database.types.UTCDateTime(timezone=True)
PRICE = app.database.types.Price


def upgrade() -> None:
    op.create_table(
        "paper_shadow_trades",
        sa.Column("trade_id", sa.Integer(), nullable=False),
        sa.Column("variant", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("exit_reason", sa.String(length=16), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("take_profit", PRICE, nullable=False),
        sa.Column("cursor_at", TS, nullable=False),
        sa.Column("fill_price", PRICE, nullable=True),
        sa.Column("filled_at", TS, nullable=True),
        sa.Column("exit_price", PRICE, nullable=True),
        sa.Column("closed_at", TS, nullable=True),
        sa.Column("risk", sa.Float(), nullable=True),
        sa.Column("r_gross", sa.Float(), nullable=True),
        sa.Column("r_net", sa.Float(), nullable=True),
        sa.Column("mfe_r", sa.Float(), nullable=True),
        sa.Column("mae_r", sa.Float(), nullable=True),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column("last_price_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(["trade_id"], ["paper_trades.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trade_id"),
    )
    op.create_index("ix_paper_shadow_trades_status", "paper_shadow_trades", ["status"])
    op.create_index("ix_paper_shadow_trades_closed_at", "paper_shadow_trades", ["closed_at"])


def downgrade() -> None:
    op.drop_index("ix_paper_shadow_trades_closed_at", table_name="paper_shadow_trades")
    op.drop_index("ix_paper_shadow_trades_status", table_name="paper_shadow_trades")
    op.drop_table("paper_shadow_trades")
