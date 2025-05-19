# Re-export para facilitar importações
from app.schemas.user import (
    UserBase, UserCreate, User, UserUpdate, 
    Token, TokenData, LoginRequest, RegisterRequest,
    RefreshTokenRequest, ChangePassword
)
from app.schemas.agent import AgentBase, AgentCreate, AgentUpdate, Agent, AgentWithTools
from app.schemas.template import TemplateBase, TemplateCreate, TemplateUpdate, Template
from app.schemas.conversation import (
    ConversationBase, ConversationCreate, ConversationUpdate, 
    Conversation, ConversationWithMessages
)
from app.schemas.message import (
    MessageBase, MessageCreate, SendMessage, 
    Message, MessageWithFeedback, SemanticSearchResult
)
from app.schemas.tool import (
    ToolBase, ToolCreate, ToolUpdate, Tool,
    AgentToolMappingBase, AgentToolMappingCreate, 
    AgentToolMappingUpdate, AgentToolMapping
)
from app.schemas.metrics import (
    UserFeedbackBase, UserFeedbackCreate, UserFeedback,
    AgentMetricsBase, AgentMetricsCreate, AgentMetrics,
    AgentPerformanceSummary
)
from app.schemas.embedding import EmbeddingBase, EmbeddingCreate, Embedding