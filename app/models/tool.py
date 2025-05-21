from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
import uuid

class ToolType(str, enum.Enum):
    EMAIL = "email"
    CALENDAR = "calendar"
    DOCUMENT = "document"
    CUSTOM = "custom"

class Tool(Base):
    __tablename__ = "tools"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    type = Column(SQLEnum(ToolType), nullable=False)
    configuration = Column(JSON, nullable=False, default={})
    is_active = Column(Boolean, default=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Relacionamentos
    user = relationship("User", back_populates="tools")
    agent_mappings = relationship("AgentToolMapping", back_populates="tool")
    organization = relationship("Organization", back_populates="tools")