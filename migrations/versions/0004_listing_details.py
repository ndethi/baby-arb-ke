"""Add listings.details: the model's guess, looked-up facts and a KE price ref (JSON).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-27 11:21:19.655886
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('details', sqlmodel.sql.sqltypes.AutoString(), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.drop_column('details')

