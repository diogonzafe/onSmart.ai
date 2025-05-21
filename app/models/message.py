from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, ForeignKey, JSON, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
import uuid

class MessageRole(str, enum.Enum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    meta_data = Column(JSON, nullable=True)  # Alterar de metadata para meta_data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relacionamentos
    conversation = relationship("Conversation", back_populates="messages")
    embedding = relationship("MessageEmbedding", uselist=False, back_populates="message", cascade="all, delete-orphan")
    feedback = relationship("UserFeedback", uselist=False, back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
    Index('idx_messages_conversation', conversation_id),
    Index('idx_messages_conversation_created', conversation_id, created_at),
)