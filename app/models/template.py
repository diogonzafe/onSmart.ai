from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, JSON, Text, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
import uuid

class TemplateDepartment(str, enum.Enum):
    MARKETING = "marketing"
    SALES = "sales"
    FINANCE = "finance"
    CUSTOM = "custom"

class Template(Base):
    __tablename__ = "templates"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    department = Column(SQLEnum(TemplateDepartment), default=TemplateDepartment.CUSTOM, nullable=False)
    is_public = Column(Boolean, default=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # Null para templates do sistema
    prompt_template = Column(Text, nullable=False)
    tools_config = Column(JSON, nullable=False, default={})
    llm_config = Column(JSON, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)  # Null para templates do sistema
    is_draft = Column(Boolean, default=True)
    version_number = Column(Integer, default=1)
    parent_version_id = Column(String, ForeignKey("templates.id"), nullable=True)
    tags = Column(JSON, default=list)  # Lista de tags
    category = Column(String, nullable=True)  # Categoria além do departamento
    
    # Relacionamentos
    user = relationship("User", back_populates="templates")
    agents = relationship("Agent", back_populates="template")
    organization = relationship("Organization", back_populates="templates")
    parent_version = relationship("Template", remote_side=[id], backref="child_versions")
