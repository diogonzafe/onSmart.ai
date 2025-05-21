from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
import uuid

class AgentType(str, enum.Enum):
    SUPERVISOR = "supervisor"
    MARKETING = "marketing"
    SALES = "sales"
    FINANCE = "finance"
    CUSTOM = "custom"

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Relacionamentos
    user = relationship("User", back_populates="agents")
    template = relationship("Template", back_populates="agents")
    conversations = relationship("Conversation", back_populates="agent")
    tool_mappings = relationship("AgentToolMapping", back_populates="agent")
    organization = relationship("Organization", back_populates="agents")