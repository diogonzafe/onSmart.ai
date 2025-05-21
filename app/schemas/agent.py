# app/schemas/agent.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from app.models.agent import AgentType

# Base schema para agentes
class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    agent_type: AgentType
    configuration: Dict[str, Any] = Field(default_factory=dict)

# Para criação de agentes
class AgentCreate(AgentBase):
    template_id: str

# Para atualização de agentes
class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    configuration: Optional[Dict[str, Any]] = None

# Para atualizações em lote de agentes
class AgentBatchUpdate(BaseModel):
    agent_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    configuration: Optional[Dict[str, Any]] = None

# Para respostas de agentes
class Agent(AgentBase):
    id: str
    user_id: str
    template_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Modelo de agente com ferramentas incluídas
class AgentWithTools(Agent):
    tools: List[Any] = []
    
    class Config:
        from_attributes = True