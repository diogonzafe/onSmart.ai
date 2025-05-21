from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
import uuid

class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE)
    meta_data = Column(JSON, nullable=True)  # Alterar de metadata para meta_data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    user = relationship("User", back_populates="conversations")
    agent = relationship("Agent", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
    Index('idx_conversations_user_status', user_id, status),
)