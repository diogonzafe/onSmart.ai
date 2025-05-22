# app/models/__init__.py - Versão corrigida
# Importar modelos na ordem correta para evitar problemas de relacionamento

# Primeiro, importar o modelo base
from app.db.database import Base

# Importar o modelo Organization primeiro (não tem dependências)
from app.models.organization import Organization

# Depois importar User (depende de Organization)
from app.models.user import User, AuthProvider

# Importar Template (depende de User e Organization)
from app.models.template import Template, TemplateDepartment

# Importar Agent (depende de User, Template e Organization)
from app.models.agent import Agent, AgentType

# Importar Conversation (depende de User e Agent)
from app.models.conversation import Conversation, ConversationStatus

# Importar Message (depende de Conversation)
from app.models.message import Message, MessageRole

# Importar Embedding (depende de Message)
from app.models.embedding import MessageEmbedding

# Importar Tool (depende de User e Organization)
from app.models.tool import Tool, ToolType

# Importar AgentToolMapping (depende de Agent e Tool)
from app.models.agent_tool_mapping import AgentToolMapping

# Importar Metrics (depende de Agent, User, Conversation, Message)
from app.models.metrics import AgentMetrics, UserFeedback

# Lista de todos os modelos para facilitar importações
__all__ = [
    'Base',
    'Organization',
    'User', 'AuthProvider',
    'Template', 'TemplateDepartment', 
    'Agent', 'AgentType',
    'Conversation', 'ConversationStatus',
    'Message', 'MessageRole',
    'MessageEmbedding',
    'Tool', 'ToolType',
    'AgentToolMapping',
    'AgentMetrics', 'UserFeedback'
]