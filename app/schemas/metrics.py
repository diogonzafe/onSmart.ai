from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

# Feedback
class UserFeedbackBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)  # Rating de 1 a 5
    feedback_text: Optional[str] = None

class UserFeedbackCreate(UserFeedbackBase):
    pass

class UserFeedback(UserFeedbackBase):
    id: str
    message_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Métricas de agente
class AgentMetricsBase(BaseModel):
    response_time: float
    tools_used: Optional[Dict[str, Any]] = None
    llm_tokens: Optional[int] = None

class AgentMetricsCreate(AgentMetricsBase):
    agent_id: str
    conversation_id: str

class AgentMetrics(AgentMetricsBase):
    id: str
    agent_id: str
    user_id: str
    conversation_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Agregação de métricas
class AgentPerformanceSummary(BaseModel):
    agent_id: str
    agent_name: str
    avg_response_time: float
    total_conversations: int
    total_messages: int
    avg_rating: Optional[float] = None
    tools_usage: Dict[str, int]
    period_start: datetime
    period_end: datetime