from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid

class AgentToolMapping(Base):
    __tablename__ = "agent_tool_mappings"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    tool_id = Column(String, ForeignKey("tools.id"), nullable=False)
    permissions = Column(JSON, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    agent = relationship("Agent", back_populates="tool_mappings")
    tool = relationship("Tool", back_populates="agent_mappings")