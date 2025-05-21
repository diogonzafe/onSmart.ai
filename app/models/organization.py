# app/models/organization.py
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    settings = Column(JSON, nullable=False, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    users = relationship("User", back_populates="organization")
    agents = relationship("Agent", back_populates="organization")
    templates = relationship("Template", back_populates="organization")
    tools = relationship("Tool", back_populates="organization")