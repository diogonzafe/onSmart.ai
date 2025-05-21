# app/models/conversation.py - Adicionar índices

from sqlalchemy import Index

# Índice para busca rápida por usuário e status
__table_args__ = (
    Index('idx_conversations_user_status', 'user_id', 'status'),
)

# app/models/message.py - Adicionar índices

# Índice para busca rápida por conversa
__table_args__ = (
    Index('idx_messages_conversation', 'conversation_id'),
    Index('idx_messages_conversation_created', 'conversation_id', 'created_at'),
)

# Adicionar script para criar índices via Alembic

# migrations/versions/XXXXXX_add_indices.py
"""add indices

Revision ID: XXXXXX
Revises: previous_revision
Create Date: 2023-05-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'XXXXXX'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None

def upgrade():
    # Índices para conversas
    op.create_index('idx_conversations_user_status', 'conversations', ['user_id', 'status'])
    op.create_index('idx_conversations_agent', 'conversations', ['agent_id'])
    op.create_index('idx_conversations_org', 'conversations', ['organization_id'])
    
    # Índices para mensagens
    op.create_index('idx_messages_conversation', 'messages', ['conversation_id'])
    op.create_index('idx_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])
    
    # Índices para agentes
    op.create_index('idx_agents_org_type', 'agents', ['organization_id', 'type'])
    op.create_index('idx_agents_user', 'agents', ['user_id'])
    
    # Índices para templates
    op.create_index('idx_templates_org_dept', 'templates', ['organization_id', 'department'])
    op.create_index('idx_templates_public', 'templates', ['is_public'])

def downgrade():
    # Remover índices
    op.drop_index('idx_conversations_user_status')
    op.drop_index('idx_conversations_agent')
    op.drop_index('idx_conversations_org')
    op.drop_index('idx_messages_conversation')
    op.drop_index('idx_messages_conversation_created')
    op.drop_index('idx_agents_org_type')
    op.drop_index('idx_agents_user')
    op.drop_index('idx_templates_org_dept')
    op.drop_index('idx_templates_public')