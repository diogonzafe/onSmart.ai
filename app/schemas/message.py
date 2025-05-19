from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from app.models.message import MessageRole

# Base schema
class MessageBase(BaseModel):
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = None

# Para criação
class MessageCreate(MessageBase):
    pass

# Request para enviar mensagem para um agente
class SendMessage(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None

# Para respostas
class Message(MessageBase):
    id: str
    conversation_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Com feedback incluído
class MessageWithFeedback(Message):
    feedback: Optional["UserFeedback"] = None
    
    class Config:
        from_attributes = True

# Resposta para busca semântica
class SemanticSearchResult(BaseModel):
    messages: List[Message]
    similarity_scores: List[float]

# Resolução da referência circular - COLOQUE ISSO NO FINAL DO ARQUIVO
from app.schemas.metrics import UserFeedback
MessageWithFeedback.model_rebuild()