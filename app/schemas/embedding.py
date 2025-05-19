from pydantic import BaseModel
from typing import List, Optional
import numpy as np

class EmbeddingBase(BaseModel):
    message_id: str
    
class EmbeddingCreate(EmbeddingBase):
    embedding: List[float]
    
class Embedding(EmbeddingBase):
    id: str
    
    class Config:
        from_attributes = True