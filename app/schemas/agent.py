# app/schemas/agent.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
from app.models.agent import AgentType

# Base schema para agentes
class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    agent_type: AgentType
    configuration: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('agent_type', pre=True)
    def validate_agent_type(cls, v):
        """Valida e normaliza o tipo de agente."""
        if isinstance(v, str):
            # Converter para lowercase para garantir consistência
            v = v.lower()
            # Verificar se é um valor válido
            valid_values = [e.value for e in AgentType]
            if v not in valid_values:
                raise ValueError(f"agent_type deve ser um dos: {', '.join(valid_values)}")
            return v
        elif isinstance(v, AgentType):
            return v.value
        else:
            raise ValueError("agent_type deve ser uma string ou AgentType")

# Para criação de agentes
class AgentCreate(AgentBase):
    template_id: str
    
    class Config:
        # Exemplo de uso
        schema_extra = {
            "example": {
                "name": "Agente de Marketing",
                "description": "Agente especializado em marketing digital",
                "agent_type": "marketing",
                "template_id": "template-123",
                "configuration": {
                    "company_name": "TechCorp",
                    "primary_platform": "LinkedIn",
                    "brand_tone": "profissional"
                }
            }
        }

# Para atualização de agentes
class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    configuration: Optional[Dict[str, Any]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Novo Nome do Agente",
                "description": "Nova descrição",
                "is_active": True,
                "configuration": {
                    "updated_setting": "new_value"
                }
            }
        }

# Para atualizações em lote de agentes
class AgentBatchUpdate(BaseModel):
    agent_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    configuration: Optional[Dict[str, Any]] = None
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        """Valida se o agent_id não está vazio."""
        if not v or not v.strip():
            raise ValueError("agent_id é obrigatório e não pode estar vazio")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "agent_id": "agent-123",
                "name": "Nome Atualizado",
                "is_active": True
            }
        }

# Para respostas de agentes (RENOMEADO PARA AgentResponse)
class AgentResponse(AgentBase):
    id: str
    user_id: str
    template_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    @validator('agent_type', pre=True)
    def validate_agent_type_response(cls, v):
        """Valida o tipo de agente para respostas."""
        if isinstance(v, AgentType):
            return v.value
        return v
    
    class Config:
        from_attributes = True
        # Permitir enums serem serializados como valores
        use_enum_values = True

# Alias para manter compatibilidade com código existente
Agent = AgentResponse

# Modelo de agente com ferramentas incluídas
class AgentWithTools(AgentResponse):
    tools: List[Any] = []
    
    class Config:
        from_attributes = True
        use_enum_values = True

# Schema para resposta de criação em lote
class AgentBatchResponse(BaseModel):
    success_count: int
    error_count: int
    results: List[Dict[str, Any]]
    
    class Config:
        schema_extra = {
            "example": {
                "success_count": 2,
                "error_count": 0,
                "results": [
                    {
                        "id": "agent-1",
                        "status": "success",
                        "message": "Agente criado com sucesso"
                    },
                    {
                        "id": "agent-2", 
                        "status": "success",
                        "message": "Agente criado com sucesso"
                    }
                ]
            }
        }

# Schema para validação de configuração de agente
class AgentConfiguration(BaseModel):
    """Schema para validar configurações específicas de agentes."""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    priority: Optional[str] = None
    
    # Configurações específicas para Marketing
    primary_platform: Optional[str] = None
    brand_tone: Optional[str] = None
    target_audience: Optional[str] = None
    differentials: Optional[str] = None
    metric_priority: Optional[str] = None
    especialidade: Optional[str] = None
    
    # Configurações específicas para Sales
    product_category: Optional[str] = None
    products_list: Optional[str] = None
    sales_style: Optional[str] = None
    sales_priority: Optional[str] = None
    pricing_policy: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_time: Optional[str] = None
    return_policy: Optional[str] = None
    discount_level: Optional[str] = None
    
    # Configurações específicas para Finance
    analysis_type: Optional[str] = None
    competitors: Optional[str] = None
    key_indicators: Optional[str] = None
    analysis_period: Optional[str] = None
    currency: Optional[str] = None
    accounting_standards: Optional[str] = None
    analysis_methodology: Optional[str] = None
    
    class Config:
        extra = "allow"  # Permitir campos adicionais
        schema_extra = {
            "example": {
                "company_name": "TechCorp",
                "industry": "Tecnologia",
                "primary_platform": "LinkedIn",
                "brand_tone": "profissional"
            }
        }

# Schema para status de processamento de agente
class AgentProcessingStatus(BaseModel):
    agent_id: str
    status: str
    processing_time: Optional[float] = None
    error: Optional[str] = None
    last_activity: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "agent_id": "agent-123",
                "status": "ready",
                "processing_time": 1.23,
                "last_activity": "2025-01-21T10:30:00Z"
            }
        }