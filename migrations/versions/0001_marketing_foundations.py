"""Marketing foundations: listing store, safety verdicts, llm_calls, bot state.

ENGINE_SPEC section 7, Phase 0 tables. Phase 1 adds renders, edit_events,
schedule and notices in 0002.

Revision ID: 0001
Revises:
Create Date: 2026-11-21 10:27:07.231766
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('bot_state',
    sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('code_counters',
    sa.Column('prefix', sqlmodel.sql.sqltypes.AutoString(length=1), nullable=False),
    sa.Column('last', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('prefix')
    )
    op.create_table('listings',
    sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('brand', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('model_source', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
    sa.Column('model_confidence', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('age_range', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('grade', sqlmodel.sql.sqltypes.AutoString(length=1), nullable=True),
    sa.Column('condition_note', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('buy_price', sa.Integer(), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.Column('price_source', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
    sa.Column('ref_new_price', sa.Integer(), nullable=True),
    sa.Column('seller_id', sa.Integer(), nullable=True),
    sa.Column('template_version', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('live_at', sa.DateTime(), nullable=True),
    sa.Column('sold_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('code')
    )
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_listings_status'), ['status'], unique=False)

    op.create_table('llm_calls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('purpose', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('tokens_in', sa.Integer(), nullable=False),
    sa.Column('tokens_out', sa.Integer(), nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=False),
    sa.Column('error', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('llm_calls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_llm_calls_at'), ['at'], unique=False)

    op.create_table('listing_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('from_status', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('to_status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('actor', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('note', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['listing_code'], ['listings.code'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('listing_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_listing_events_listing_code'), ['listing_code'], unique=False)

    op.create_table('photos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('n', sa.Integer(), nullable=False),
    sa.Column('path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('is_hero', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['listing_code'], ['listings.code'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('listing_code', 'n')
    )
    with op.batch_alter_table('photos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_photos_listing_code'), ['listing_code'], unique=False)

    op.create_table('safety_verdicts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('verdict', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('reasons', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('recall_source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('override_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['listing_code'], ['listings.code'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('safety_verdicts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_safety_verdicts_listing_code'), ['listing_code'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('safety_verdicts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_safety_verdicts_listing_code'))

    op.drop_table('safety_verdicts')
    with op.batch_alter_table('photos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_photos_listing_code'))

    op.drop_table('photos')
    with op.batch_alter_table('listing_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_listing_events_listing_code'))

    op.drop_table('listing_events')
    with op.batch_alter_table('llm_calls', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_llm_calls_at'))

    op.drop_table('llm_calls')
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_listings_status'))

    op.drop_table('listings')
    op.drop_table('code_counters')
    op.drop_table('bot_state')
