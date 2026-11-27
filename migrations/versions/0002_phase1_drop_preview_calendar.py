"""Phase 1: schedule, renders, edit_events; listing render state and captions.

ENGINE_SPEC sections 4 and 7. `listings.round` gets a server default so the
migration runs on a database that already holds listings.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-27 09:24:54.502801
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('edit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('raw_text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('op', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('target', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('before', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('after', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('parsed_by', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['listing_code'], ['listings.code'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('edit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_edit_events_listing_code'), ['listing_code'], unique=False)

    op.create_table('renders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('asset', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('template_version', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['listing_code'], ['listings.code'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('renders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_renders_listing_code'), ['listing_code'], unique=False)

    op.create_table('schedule',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('slot_at', sa.DateTime(), nullable=False),
    sa.Column('channels', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
    sa.Column('proposed_by', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('moved_from', sa.DateTime(), nullable=True),
    sa.Column('reminded_at', sa.DateTime(), nullable=True),
    sa.Column('posted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['listing_code'], ['listings.code'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('schedule', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_schedule_listing_code'), ['listing_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_schedule_slot_at'), ['slot_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_schedule_status'), ['status'], unique=False)

    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('layout', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('caption_ig', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('caption_tiktok', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(
            sa.Column('round', sa.Integer(), nullable=False, server_default=sa.text('0'))
        )
        batch_op.add_column(sa.Column('created_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.drop_column('created_by')
        batch_op.drop_column('round')
        batch_op.drop_column('caption_tiktok')
        batch_op.drop_column('caption_ig')
        batch_op.drop_column('layout')

    with op.batch_alter_table('schedule', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_schedule_status'))
        batch_op.drop_index(batch_op.f('ix_schedule_slot_at'))
        batch_op.drop_index(batch_op.f('ix_schedule_listing_code'))

    op.drop_table('schedule')
    with op.batch_alter_table('renders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_renders_listing_code'))

    op.drop_table('renders')
    with op.batch_alter_table('edit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_edit_events_listing_code'))

    op.drop_table('edit_events')
