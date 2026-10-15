"""add_coach_conversations_schema

Revision ID: 4c5d6e7f8a9b
Revises: 3b4c5d6e7f8a
Create Date: 2026-08-22 17:16:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c5d6e7f8a9b'
down_revision: Union[str, Sequence[str], None] = '3b4c5d6e7f8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create coach_conversations table
    op.create_table(
        'coach_conversations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='Knowledge Mesh Coaching Session'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_coach_conversations_user_id'), 'coach_conversations', ['user_id'], unique=False)

    # Create coach_messages table
    op.create_table(
        'coach_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('sender', sa.String(length=32), nullable=False, server_default='ai'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('context_used', sa.JSON(), nullable=True),
        sa.Column('evidence_references', sa.JSON(), nullable=True),
        sa.Column('suggested_actions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['coach_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_coach_messages_conversation_id'), 'coach_messages', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_coach_messages_conversation_id'), table_name='coach_messages')
    op.drop_table('coach_messages')
    op.drop_index(op.f('ix_coach_conversations_user_id'), table_name='coach_conversations')
    op.drop_table('coach_conversations')
