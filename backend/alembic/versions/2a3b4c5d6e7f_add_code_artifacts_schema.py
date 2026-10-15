"""add_code_artifacts_schema

Revision ID: 2a3b4c5d6e7f
Revises: 12eac25f30bc
Create Date: 2026-08-22 17:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a3b4c5d6e7f'
down_revision: Union[str, Sequence[str], None] = '12eac25f30bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create code_artifacts table
    op.create_table(
        'code_artifacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('platform_connection_id', sa.String(length=36), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=False, server_default='GitHub'),
        sa.Column('repository', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('source_url', sa.String(length=512), nullable=True),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('language', sa.String(length=64), nullable=False),
        sa.Column('code_content', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['platform_connection_id'], ['platform_connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_code_artifacts_user_id'), 'code_artifacts', ['user_id'], unique=False)
    op.create_index(op.f('ix_code_artifacts_platform_connection_id'), 'code_artifacts', ['platform_connection_id'], unique=False)

    # Create code_analyses table
    op.create_table(
        'code_analyses',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code_artifact_id', sa.String(length=36), nullable=False),
        sa.Column('language', sa.String(length=64), nullable=False),
        sa.Column('lines_of_code', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('function_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('class_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cyclomatic_complexity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('has_recursion', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('detected_concepts', sa.JSON(), nullable=True),
        sa.Column('data_structures', sa.JSON(), nullable=True),
        sa.Column('analysis_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['code_artifact_id'], ['code_artifacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_artifact_id')
    )
    op.create_index(op.f('ix_code_analyses_code_artifact_id'), 'code_analyses', ['code_artifact_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_code_analyses_code_artifact_id'), table_name='code_analyses')
    op.drop_table('code_analyses')
    op.drop_index(op.f('ix_code_artifacts_platform_connection_id'), table_name='code_artifacts')
    op.drop_index(op.f('ix_code_artifacts_user_id'), table_name='code_artifacts')
    op.drop_table('code_artifacts')
