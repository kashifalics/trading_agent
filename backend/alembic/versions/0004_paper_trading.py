"""paper trading: simulated account and forward-tested signals

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07 21:30:00
"""
from alembic import op
import sqlalchemy as sa
import app.database.types
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql')
TS = app.database.types.UTCDateTime(timezone=True)
PRICE = sa.Numeric(precision=28, scale=10)


def upgrade() -> None:
    op.create_table('paper_accounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('start_balance', sa.Float(), nullable=False),
    sa.Column('risk_pct', sa.Float(), nullable=False),
    sa.Column('max_open_positions', sa.Integer(), nullable=False),
    sa.Column('max_daily_loss_pct', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', TS, nullable=False),
    sa.Column('closed_at', TS, nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('paper_accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_paper_accounts_is_active'), ['is_active'], unique=False)

    op.create_table('paper_trades',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.Column('instrument_id', sa.Integer(), nullable=False),
    sa.Column('provider_id', sa.Integer(), nullable=True),
    sa.Column('symbol', sa.String(length=16), nullable=False),
    sa.Column('timeframe', sa.String(length=4), nullable=False),
    sa.Column('setup_key', sa.String(length=200), nullable=False),
    sa.Column('direction', sa.String(length=4), nullable=False),
    sa.Column('order_type', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('exit_reason', sa.String(length=16), nullable=True),
    sa.Column('note', sa.String(length=200), nullable=True),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('grade', sa.String(length=2), nullable=True),
    sa.Column('setup_type', sa.String(length=32), nullable=True),
    sa.Column('entry_type', sa.String(length=16), nullable=True),
    sa.Column('session', sa.String(length=32), nullable=True),
    sa.Column('signal_ts', TS, nullable=False),
    sa.Column('detected_at', TS, nullable=False),
    sa.Column('valid_until', TS, nullable=False),
    sa.Column('entry_price', PRICE, nullable=False),
    sa.Column('stop_loss', PRICE, nullable=False),
    sa.Column('take_profit', PRICE, nullable=False),
    sa.Column('invalidation', PRICE, nullable=True),
    sa.Column('planned_rr', sa.Float(), nullable=True),
    sa.Column('fill_price', PRICE, nullable=True),
    sa.Column('filled_at', TS, nullable=True),
    sa.Column('exit_price', PRICE, nullable=True),
    sa.Column('closed_at', TS, nullable=True),
    sa.Column('risk', sa.Float(), nullable=True),
    sa.Column('spread', sa.Float(), nullable=False),
    sa.Column('r_gross', sa.Float(), nullable=True),
    sa.Column('r_net', sa.Float(), nullable=True),
    sa.Column('mfe_r', sa.Float(), nullable=True),
    sa.Column('mae_r', sa.Float(), nullable=True),
    sa.Column('cursor_at', TS, nullable=False),
    sa.Column('last_price', sa.Float(), nullable=True),
    sa.Column('last_price_at', TS, nullable=True),
    sa.Column('account_taken', sa.Boolean(), nullable=False),
    sa.Column('account_note', sa.String(length=160), nullable=True),
    sa.Column('risk_amount', sa.Float(), nullable=True),
    sa.Column('pnl', sa.Float(), nullable=True),
    sa.Column('plan', JSON, nullable=True),
    sa.Column('config_version', sa.String(length=32), nullable=True),
    sa.Column('created_at', TS, nullable=False),
    sa.Column('updated_at', TS, nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ),
    sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
    sa.ForeignKeyConstraint(['provider_id'], ['data_providers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('instrument_id', 'timeframe', 'setup_key', name='uq_paper_signal')
    )
    with op.batch_alter_table('paper_trades', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_paper_trades_account_id'), ['account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_paper_trades_closed_at'), ['closed_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_paper_trades_detected_at'), ['detected_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_paper_trades_instrument_id'), ['instrument_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_paper_trades_status'), ['status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('paper_trades', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_paper_trades_status'))
        batch_op.drop_index(batch_op.f('ix_paper_trades_instrument_id'))
        batch_op.drop_index(batch_op.f('ix_paper_trades_detected_at'))
        batch_op.drop_index(batch_op.f('ix_paper_trades_closed_at'))
        batch_op.drop_index(batch_op.f('ix_paper_trades_account_id'))

    op.drop_table('paper_trades')
    with op.batch_alter_table('paper_accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_paper_accounts_is_active'))

    op.drop_table('paper_accounts')
