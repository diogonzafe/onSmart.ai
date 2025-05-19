from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid
import pgvector.sqlalchemy

class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    embedding = Column(pgvector.sqlalchemy.Vector(1536))  # Use pgvector.sqlalchemy em vez de sqlalchemy_pgvector
    
    # Relacionamentos
    message = relationship("Message", back_populates="embedding")