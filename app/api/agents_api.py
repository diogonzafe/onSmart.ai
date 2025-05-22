# app/api/agents_api.py - Correções para o problema de conversation_id null

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.db.database import get_db
from app.models.agent import Agent, AgentType
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.schemas.agent import AgentResponse
from app.schemas.message import SendMessage
from app.services.agent_service import get_agent_service
from app.core.security import get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/api/agents", tags=["agents"])

# CORREÇÃO: Endpoint melhorado para envio de mensagens
@router.post("/{agent_id}/message")
async def send_message_to_agent(
    agent_id: str,
    message_data: SendMessage,
    conversation_id: Optional[str] = None,  # Tornar opcional
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Envia uma mensagem para um agente específico.
    Cria uma nova conversa automaticamente se não for fornecida.
    """
    try:
        # Verificar se o agente existe e pertence ao usuário
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.user_id == current_user.id,
            Agent.is_active == True
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agente não encontrado ou inativo"
            )
        
        # Se conversation_id não foi fornecido ou é inválido, criar nova conversa
        if not conversation_id or conversation_id == "null":
            conversation = Conversation(
                id=str(uuid.uuid4()),
                title=f"Conversa com {agent.name}",
                user_id=current_user.id,
                agent_id=agent_id,
                status=ConversationStatus.ACTIVE,
                meta_data={
                    "auto_created": True,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            
            conversation_id = conversation.id
        else:
            # Verificar se a conversa existe e pertence ao usuário
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            ).first()
            
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversa não encontrada"
                )
        
        # Processar a mensagem
        agent_service = get_agent_service(db)
        
        response = await agent_service.process_message(
            agent_id=agent_id,
            conversation_id=conversation_id,
            message=message_data.content,
            metadata=message_data.metadata
        )
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "user_message": response["user_message"],
            "agent_response": response["agent_response"],
            "timestamp": datetime.utcnow().isoformat(),
            "auto_created_conversation": conversation_id != message_data.metadata.get('original_conversation_id') if message_data.metadata else True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar mensagem: {str(e)}"
        )

# NOVO: Endpoint para criação explícita de conversas
@router.post("/{agent_id}/conversations")
async def create_conversation_with_agent(
    agent_id: str,
    title: Optional[str] = Body(None),
    initial_message: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cria uma nova conversa com um agente específico.
    Opcionalmente envia uma mensagem inicial.
    """
    try:
        # Verificar se o agente existe e pertence ao usuário
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.user_id == current_user.id,
            Agent.is_active == True
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agente não encontrado ou inativo"
            )
        
        # Criar a conversa
        conversation_title = title or f"Conversa com {agent.name} - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=conversation_title,
            user_id=current_user.id,
            agent_id=agent_id,
            status=ConversationStatus.ACTIVE,
            meta_data={
                "explicit_creation": True,
                "agent_type": agent.type.value
            }
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        # Se há mensagem inicial, processá-la
        response_data = {
            "conversation_id": conversation.id,
            "conversation_title": conversation.title,
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "type": agent.type.value
            },
            "created_at": conversation.created_at.isoformat()
        }
        
        if initial_message:
            agent_service = get_agent_service(db)
            
            message_response = await agent_service.process_message(
                agent_id=agent_id,
                conversation_id=conversation.id,
                message=initial_message
            )
            
            response_data["initial_exchange"] = {
                "user_message": message_response["user_message"],
                "agent_response": message_response["agent_response"]
            }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar conversa: {str(e)}"
        )

# NOVO: Endpoint para listar conversas de um agente
@router.get("/{agent_id}/conversations")
async def list_agent_conversations(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[ConversationStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Lista as conversas de um agente específico.
    """
    try:
        # Verificar se o agente existe e pertence ao usuário
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.user_id == current_user.id
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agente não encontrado"
            )
        
        # Construir query
        query = db.query(Conversation).filter(
            Conversation.agent_id == agent_id,
            Conversation.user_id == current_user.id
        )
        
        if status:
            query = query.filter(Conversation.status == status)
        
        # Obter total e aplicar paginação
        total = query.count()
        conversations = query.order_by(
            Conversation.updated_at.desc()
        ).offset(offset).limit(limit).all()
        
        # Preparar resposta
        items = []
        for conv in conversations:
            # Contar mensagens
            message_count = db.query(Message).filter(
                Message.conversation_id == conv.id
            ).count()
            
            # Última mensagem
            last_message = db.query(Message).filter(
                Message.conversation_id == conv.id
            ).order_by(Message.created_at.desc()).first()
            
            items.append({
                "id": conv.id,
                "title": conv.title,
                "status": conv.status.value,
                "message_count": message_count,
                "last_message": {
                    "content": last_message.content[:100] + "..." if last_message and len(last_message.content) > 100 else last_message.content if last_message else None,
                    "role": last_message.role.value if last_message else None,
                    "created_at": last_message.created_at.isoformat() if last_message else None
                } if last_message else None,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat()
            })
        
        return {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "type": agent.type.value
            },
            "conversations": {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar conversas: {str(e)}"
        )