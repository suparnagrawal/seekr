"""add graph_job_status enum

Revision ID: d58ac1849c7c
Revises: 66ea9fe97ae0
Create Date: 2026-07-11 11:48:43.134787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd58ac1849c7c'
down_revision: Union[str, Sequence[str], None] = '66ea9fe97ae0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Since the column might have been added manually as VARCHAR in the DB for the MVP, 
    # we use IF NOT EXISTS logic or ALTER column. 
    # For safety, we drop it and recreate it as the proper ENUM type.
    
    # Create ENUM type
    graph_job_status_enum = sa.Enum('SUCCESS', 'FAILED', 'SKIPPED', name='graphjobstatus')
    graph_job_status_enum.create(op.get_bind(), checkfirst=True)
    
    bind = op.get_bind()
    insp = sa.inspect(bind)
    has_column = False
    if 'documents' in insp.get_table_names():
        has_column = any(c['name'] == 'graph_job_status' for c in insp.get_columns('documents'))
        
    if has_column:
        op.execute(
            "ALTER TABLE documents ALTER COLUMN graph_job_status "
            "TYPE graphjobstatus USING graph_job_status::text::graphjobstatus"
        )
    else:
        op.add_column('documents', sa.Column('graph_job_status', graph_job_status_enum, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'graph_job_status')
    graph_job_status_enum = sa.Enum('SUCCESS', 'FAILED', 'SKIPPED', name='graphjobstatus')
    graph_job_status_enum.drop(op.get_bind(), checkfirst=True)
