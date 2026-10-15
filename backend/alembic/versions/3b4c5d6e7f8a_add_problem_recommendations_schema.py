"""add_problem_recommendations_schema

Revision ID: 3b4c5d6e7f8a
Revises: 2a3b4c5d6e7f
Create Date: 2026-08-22 17:11:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b4c5d6e7f8a'
down_revision: Union[str, Sequence[str], None] = '2a3b4c5d6e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create problems table
    op.create_table(
        'problems',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=False, server_default='GitHub'),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=512), nullable=True),
        sa.Column('difficulty', sa.String(length=32), nullable=False, server_default='Easy'),
        sa.Column('topics', sa.JSON(), nullable=True),
        sa.Column('language', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=False, server_default='Permitted Platform Reference'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create problem_recommendations table
    op.create_table(
        'problem_recommendations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('problem_id', sa.String(length=36), nullable=False),
        sa.Column('target_skill_slug', sa.String(length=128), nullable=False),
        sa.Column('prerequisite_skill_slug', sa.String(length=128), nullable=True),
        sa.Column('recommendation_reason', sa.Text(), nullable=False),
        sa.Column('evidence_strength', sa.String(length=32), nullable=False, server_default='Limited'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_problem_recommendations_user_id'), 'problem_recommendations', ['user_id'], unique=False)
    op.create_index(op.f('ix_problem_recommendations_problem_id'), 'problem_recommendations', ['problem_id'], unique=False)

    # Create code_attempts table
    op.create_table(
        'code_attempts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('problem_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='attempted'),
        sa.Column('source_platform', sa.String(length=32), nullable=False, server_default='GitHub'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_code_attempts_user_id'), 'code_attempts', ['user_id'], unique=False)
    op.create_index(op.f('ix_code_attempts_problem_id'), 'code_attempts', ['problem_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_code_attempts_problem_id'), table_name='code_attempts')
    op.drop_index(op.f('ix_code_attempts_user_id'), table_name='code_attempts')
    op.drop_table('code_attempts')
    op.drop_index(op.f('ix_problem_recommendations_problem_id'), table_name='problem_recommendations')
    op.drop_index(op.f('ix_problem_recommendations_user_id'), table_name='problem_recommendations')
    op.drop_table('problem_recommendations')
    op.drop_table('problems')
