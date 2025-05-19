from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from app.models.template import TemplateDepartment

# Base schema
class TemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    department: TemplateDepartment
    is_public: bool = False
    prompt_template: str
    tools_config: Dict[str, Any] = Field(default_factory=dict)
    llm_config: Dict[str, Any] = Field(default_factory=dict)

# Para criação
class TemplateCreate(TemplateBase):
    pass

# Para atualização
class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    department: Optional[TemplateDepartment] = None
    is_public: Optional[bool] = None
    prompt_template: Optional[str] = None
    tools_config: Optional[Dict[str, Any]] = None
    llm_config: Optional[Dict[str, Any]] = None

# Para respostas
class Template(TemplateBase):
    id: str
    user_id: Optional[str] = None  # Pode ser null para templates do sistema
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True