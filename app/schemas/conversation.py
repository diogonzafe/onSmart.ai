from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from app.models.conversation import ConversationStatus

# Base schema
class ConversationBase(BaseModel):
    title: str
    metadata: Optional[Dict[str, Any]] = None

# Para criação
class ConversationCreate(ConversationBase):
    agent_id: str

# Para atualização
class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[ConversationStatus] = None
    metadata: Optional[Dict[str, Any]] = None

# Para respostas
class Conversation(ConversationBase):
    id: str
    user_id: str
    agent_id: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Com mensagens incluídas
class ConversationWithMessages(Conversation):
    messages: List["Message"] = []
    
    class Config:
        from_attributes = True

# Resolução da referência circular - COLOQUE ISSO NO FINAL DO ARQUIVO
from app.schemas.message import Message
ConversationWithMessages.model_rebuild()