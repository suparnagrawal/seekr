"""extend_facts_schema

Revision ID: a7b3c1d2e4f5
Revises: d58ac1849c7c
Create Date: 2026-07-20 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'a7b3c1d2e4f5'
down_revision: Union[str, Sequence[str], None] = 'd58ac1849c7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Extend the facts table with columns for compositional reasoning support.
    
    - object_value: literal spec values (e.g. "4in", "316SS")
    - source_passage: JSONB citation provenance (page, bbox, passage text)
    - extraction_method: how the fact was extracted ("llm", "rule", "manual")
    - object_tag: made nullable to support literal-value facts
    """
    # Add new columns
    op.add_column('facts', sa.Column('object_value', sa.Text(), nullable=True))
    op.add_column('facts', sa.Column('source_passage', JSONB(), nullable=True))
    op.add_column('facts', sa.Column('extraction_method', sa.String(), nullable=True))
    
    # Make object_tag nullable (it was NOT NULL before)
    op.alter_column('facts', 'object_tag',
                    existing_type=sa.String(),
                    nullable=True)
    
    # Add audit_log table for compliance and traceability
    op.create_table('audit_log',
        sa.Column('id', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('actor', sa.String(), nullable=False, server_default='system'),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('detail', JSONB(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_log_timestamp', 'audit_log', ['timestamp'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_resource_type', 'audit_log', ['resource_type'])


def downgrade() -> None:
    """Revert facts schema extension."""
    op.drop_index('ix_audit_log_resource_type', table_name='audit_log')
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_index('ix_audit_log_timestamp', table_name='audit_log')
    op.drop_table('audit_log')
    
    op.alter_column('facts', 'object_tag',
                    existing_type=sa.String(),
                    nullable=False)
    op.drop_column('facts', 'extraction_method')
    op.drop_column('facts', 'source_passage')
    op.drop_column('facts', 'object_value')
