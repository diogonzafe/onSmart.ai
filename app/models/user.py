from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum

class AuthProvider(str, enum.Enum):
    LOCAL = "local"
    GOOGLE = "google"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=True)  # Null for OAuth users
    provider = Column(SQLEnum(AuthProvider), default=AuthProvider.LOCAL, nullable=False)
    google_id = Column(String, unique=True, nullable=True)
    picture = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    
    # Novos relacionamentos para o sistema multi-agentes
    agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")
    templates = relationship("Template", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    tools = relationship("Tool", back_populates="user", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="users")