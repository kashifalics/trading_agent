"""widen timeframe_analyses.status to 24 characters

The scanner stores 'insufficient_data' (17 characters) in a VARCHAR(16) column. SQLite ignores declared lengths, so this only
failed on PostgreSQL, where every opportunity scan with a thin timeframe was rejected and marked failed.

PostgreSQL: widening a VARCHAR is a catalogue-only change (no table rewrite, no data change).
SQLite: nothing to do (lengths are not enforced); deliberately a no-op so existing SQLite databases are not rebuilt.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-10 12:30:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.alter_column('timeframe_analyses', 'status', existing_type=sa.String(length=16), type_=sa.String(length=24),
                        existing_nullable=False)


def downgrade() -> None:
    # Fails (instead of truncating) if a stored status is longer than 16 characters.
    if op.get_bind().dialect.name == 'postgresql':
        op.alter_column('timeframe_analyses', 'status', existing_type=sa.String(length=24), type_=sa.String(length=16),
                        existing_nullable=False)
