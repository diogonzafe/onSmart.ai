from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uuid

from app.db.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message
from app.core.security import get_current_active_user
from app.schemas.conversation import ConversationCreate, ConversationUpdate, Conversation as ConversationSchema
from app.schemas.message import Message as MessageSchema

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

@router.get("/", response_model=Dict[str, Any])  # Corrigido o modelo de resposta
async def list_conversations(
    status: Optional[ConversationStatus] = None,
    agent_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista as conversas do usuário atual."""
    query = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    )
    
    if status:
        query = query.filter(Conversation.status == status)
    
    if agent_id:
        query = query.filter(Conversation.agent_id == agent_id)
    
    total = query.count()
    conversations = query.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "items": conversations,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/{conversation_id}", response_model=ConversationSchema)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtém detalhes de uma conversa específica."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    return conversation

@router.post("/", response_model=ConversationSchema)
async def create_conversation(
    conversation_data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cria uma nova conversa."""
    # Verificar se o agente existe e pertence ao usuário
    from app.models.agent import Agent
    agent = db.query(Agent).filter(
        Agent.id == conversation_data.agent_id,
        Agent.user_id == current_user.id,
        Agent.is_active == True
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado ou inativo")
    
    # Criar a conversa
    conversation = Conversation(
        id=str(uuid.uuid4()),
        title=conversation_data.title,
        user_id=current_user.id,
        agent_id=conversation_data.agent_id,
        status=ConversationStatus.ACTIVE,
        metadata=conversation_data.metadata
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return conversation

@router.put("/{conversation_id}", response_model=ConversationSchema)
async def update_conversation(
    conversation_id: str,
    conversation_data: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza uma conversa existente."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Atualizar campos
    if conversation_data.title is not None:
        conversation.title = conversation_data.title
    
    if conversation_data.status is not None:
        conversation.status = conversation_data.status
    
    if conversation_data.metadata is not None:
        conversation.metadata = conversation_data.metadata
    
    db.commit()
    db.refresh(conversation)
    
    return conversation

@router.get("/{conversation_id}/messages", response_model=Dict[str, Any])  # Corrigido o modelo de resposta
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtém as mensagens de uma conversa."""
    # Verificar acesso à conversa
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Buscar mensagens
    total = db.query(Message).filter(Message.conversation_id == conversation_id).count()
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).offset(offset).limit(limit).all()
    
    return {
        "items": messages,
        "total": total,
        "limit": limit,
        "offset": offset
    }