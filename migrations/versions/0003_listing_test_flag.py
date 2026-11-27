"""Add listings.is_test: test drops are kept but left out of reports.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27 11:01:24.257598
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_test', sa.Boolean(), nullable=False, server_default=sa.false())
        )



def downgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.drop_column('is_test')

