# app/models/agent.py
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
import uuid

class AgentType(str, enum.Enum):
    """Tipos de agente disponíveis no sistema."""
    SUPERVISOR = "supervisor"
    MARKETING = "marketing"
    SALES = "sales"
    FINANCE = "finance"
    CUSTOM = "custom"
    
    @classmethod
    def get_all_values(cls):
        """Retorna todos os valores possíveis."""
        return [e.value for e in cls]
    
    @classmethod
    def is_valid(cls, value):
        """Verifica se um valor é válido para este enum."""
        return value in cls.get_all_values()
    
    def __str__(self):
        """Representação string do tipo de agente."""
        return self.value

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    type = Column(SQLEnum(AgentType), default=AgentType.CUSTOM, nullable=False)
    configuration = Column(JSON, nullable=False, default={})
    template_id = Column(String, ForeignKey("templates.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    # CORREÇÃO: Adicionar chave estrangeira para organization
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    user = relationship("User", back_populates="agents")
    template = relationship("Template", back_populates="agents")
    conversations = relationship("Conversation", back_populates="agent")
    tool_mappings = relationship("AgentToolMapping", back_populates="agent")
    # CORREÇÃO: Relacionamento com Organization agora tem chave estrangeira
    organization = relationship("Organization", back_populates="agents")
    
    def __repr__(self):
        """Representação string do agente."""
        return f"<Agent(id={self.id}, name={self.name}, type={self.type.value})>"
    
    def to_dict(self):
        """Converte o agente para dicionário."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "type": self.type.value,
            "configuration": self.configuration,
            "template_id": self.template_id,
            "is_active": self.is_active,
            "organization_id": self.organization_id,  # CORREÇÃO: Incluir no dict
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def type_display(self):
        """Nome do tipo de agente para exibição."""
        display_names = {
            AgentType.SUPERVISOR: "Supervisor",
            AgentType.MARKETING: "Marketing",
            AgentType.SALES: "Vendas",
            AgentType.FINANCE: "Financeiro",
            AgentType.CUSTOM: "Personalizado"
        }
        return display_names.get(self.type, self.type.value.title())
    
    def get_department_config(self):
        """Retorna configurações específicas do departamento."""
        dept_configs = {
            AgentType.MARKETING: {
                "required_fields": ["company_name", "primary_platform", "brand_tone"],
                "optional_fields": ["target_audience", "differentials", "metric_priority"]
            },
            AgentType.SALES: {
                "required_fields": ["company_name", "product_category", "sales_style"],
                "optional_fields": ["pricing_policy", "payment_terms", "discount_level"]
            },
            AgentType.FINANCE: {
                "required_fields": ["company_name", "analysis_type", "currency"],
                "optional_fields": ["competitors", "key_indicators", "analysis_period"]
            },
            AgentType.SUPERVISOR: {
                "required_fields": ["company_name"],
                "optional_fields": ["industry", "priority"]
            },
            AgentType.CUSTOM: {
                "required_fields": [],
                "optional_fields": []
            }
        }
        return dept_configs.get(self.type, dept_configs[AgentType.CUSTOM])
    
    def validate_configuration(self):
        """Valida a configuração do agente com base no seu tipo."""
        dept_config = self.get_department_config()
        missing_fields = []
        
        for field in dept_config["required_fields"]:
            if field not in self.configuration or not self.configuration[field]:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Campos obrigatórios ausentes para {self.type.value}: {', '.join(missing_fields)}")
        
        return True