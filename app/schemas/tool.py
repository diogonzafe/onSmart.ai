from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.tool import ToolType

# Base schema
class ToolBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: ToolType
    configuration: Dict[str, Any] = Field(default_factory=dict)

# Para criação
class ToolCreate(ToolBase):
    pass

# Para atualização
class ToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[ToolType] = None
    configuration: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

# Para respostas
class Tool(ToolBase):
    id: str
    user_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Para conexão entre agente e ferramenta
class AgentToolMappingBase(BaseModel):
    agent_id: str
    tool_id: str
    permissions: Dict[str, Any] = Field(default_factory=dict)

class AgentToolMappingCreate(AgentToolMappingBase):
    pass

class AgentToolMappingUpdate(BaseModel):
    permissions: Dict[str, Any]

class AgentToolMapping(AgentToolMappingBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True