from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid

class AgentMetrics(Base):
    __tablename__ = "agent_metrics"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    response_time = Column(Float, nullable=False)  # tempo em segundos
    tools_used = Column(JSON, nullable=True)
    llm_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relacionamentos
    agent = relationship("Agent")
    user = relationship("User")
    conversation = relationship("Conversation")

class UserFeedback(Base):
    __tablename__ = "user_feedback"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, ForeignKey("messages.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relacionamentos
    message = relationship("Message", back_populates="feedback")