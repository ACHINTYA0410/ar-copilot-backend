"""add_target_type_to_validation_runs

Revision ID: e6577519b5b2
Revises: e12325e3d4c1
Create Date: 2026-05-27 12:49:29.301445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6577519b5b2'
down_revision: Union[str, Sequence[str], None] = 'e12325e3d4c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use batch mode for SQLite compatibility (alter_column requires table rebuild)
    with op.batch_alter_table('validation_runs') as batch_op:
        batch_op.add_column(sa.Column('target_type', sa.String(10), nullable=True, server_default='deal'))
        batch_op.add_column(sa.Column('target_id', sa.String(100), nullable=True))
        # Make deal_id nullable so PO validation runs don't require a deals FK
        batch_op.alter_column('deal_id', existing_type=sa.String(20), nullable=True)

    # Backfill: existing rows are all deal runs
    op.execute("UPDATE validation_runs SET target_type = 'deal', target_id = deal_id WHERE target_id IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('validation_runs') as batch_op:
        batch_op.drop_column('target_id')
        batch_op.drop_column('target_type')
        batch_op.alter_column('deal_id', existing_type=sa.String(20), nullable=False)
