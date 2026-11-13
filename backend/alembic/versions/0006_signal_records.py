"""strategy engine v2: signal lifecycle records

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-13 12:00:00
"""
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

import app.database.types
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql')
TS = app.database.types.UTCDateTime(timezone=True)


def upgrade() -> None:
    op.create_table('signal_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('setup_key', sa.String(length=160), nullable=False),
    sa.Column('instrument_id', sa.Integer(), nullable=False),
    sa.Column('provider_id', sa.Integer(), nullable=True),
    sa.Column('symbol', sa.String(length=16), nullable=False),
    sa.Column('timeframe', sa.String(length=4), nullable=False),
    sa.Column('strategy', sa.String(length=32), nullable=False),
    sa.Column('direction', sa.String(length=4), nullable=False),
    sa.Column('regime', sa.String(length=20), nullable=True),
    sa.Column('entry_mode', sa.String(length=8), nullable=False),
    sa.Column('entry', sa.Float(), nullable=False),
    sa.Column('stop_loss', sa.Float(), nullable=False),
    sa.Column('tp1', sa.Float(), nullable=False),
    sa.Column('tp2', sa.Float(), nullable=True),
    sa.Column('tp3', sa.Float(), nullable=True),
    sa.Column('invalidation', sa.Float(), nullable=False),
    sa.Column('risk', sa.Float(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('research_status', sa.String(length=24), nullable=False),
    sa.Column('signal_time', TS, nullable=False),
    sa.Column('detected_at', TS, nullable=False),
    sa.Column('expires_at', TS, nullable=True),
    sa.Column('triggered_at', TS, nullable=True),
    sa.Column('closed_at', TS, nullable=True),
    sa.Column('cursor_at', TS, nullable=True),
    sa.Column('last_price', sa.Float(), nullable=True),
    sa.Column('best_target', sa.Integer(), nullable=False),
    sa.Column('history', JSON, nullable=False),
    sa.Column('plan', JSON, nullable=False),
    sa.Column('engine_version', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
    sa.ForeignKeyConstraint(['provider_id'], ['data_providers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('setup_key')
    )
    with op.batch_alter_table('signal_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_signal_records_instrument_id'), ['instrument_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_signal_records_symbol'), ['symbol'], unique=False)
        batch_op.create_index(batch_op.f('ix_signal_records_status'), ['status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('signal_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_signal_records_status'))
        batch_op.drop_index(batch_op.f('ix_signal_records_symbol'))
        batch_op.drop_index(batch_op.f('ix_signal_records_instrument_id'))
    op.drop_table('signal_records')
