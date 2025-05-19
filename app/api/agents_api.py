# app/api/agents_api.py
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
import uuid

from app.db.database import get_db
from app.models.user import User
from app.models.agent import Agent, AgentType
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.core.security import get_current_active_user
from app.llm.mcp_llm_service import get_mcp_llm_service

router = APIRouter(prefix="/api/agents", tags=["agents"])

@router.get("/")
async def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista todos os agentes do usuário atual."""
    agents = db.query(Agent).filter(
        Agent.user_id == current_user.id,
        Agent.is_active == True
    ).all()
    
    result = []
    for agent in agents:
        result.append({
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "type": agent.type.value,
            "template_id": agent.template_id,
            "configuration": agent.configuration
        })
    
    return result

@router.post("/conversation/{agent_id}")
async def create_conversation(
    agent_id: str,
    title: str = Body(..., embed=True),
    metadata: Optional[Dict[str, Any]] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cria uma nova conversa com um agente.
    Retorna o ID da conversa criada.
    """
    # Verificar se o agente existe e pertence ao usuário
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id,
        Agent.is_active == True
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Criar a conversa
    conversation = Conversation(
        id=str(uuid.uuid4()),
        title=title,
        user_id=current_user.id,
        agent_id=agent_id,
        status=ConversationStatus.ACTIVE,
        metadata=metadata
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return {"id": conversation.id, "title": conversation.title}

@router.post("/message/{conversation_id}")
async def send_message_to_agent(
    conversation_id: str,
    content: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Envia uma mensagem para um agente em uma conversa.
    Recebe a resposta do agente usando o protocolo MCP.
    """
    # Verificar se a conversa existe e pertence ao usuário
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
        Conversation.status == ConversationStatus.ACTIVE
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada ou inativa")
    
    # Obter o agente associado à conversa
    agent = db.query(Agent).filter(
        Agent.id == conversation.agent_id,
        Agent.is_active == True
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado ou inativo")
    
    # Registrar a mensagem do usuário
    user_message = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=MessageRole.HUMAN,
        content=content
    )
    
    db.add(user_message)
    db.commit()
    
    # Gerar resposta do agente usando o serviço MCP
    mcp_service = get_mcp_llm_service()
    
    try:
        response = await mcp_service.generate_agent_response(
            db=db,
            conversation_id=conversation_id,
            agent=agent,
            user_id=current_user.id
        )
        
        return {
            "user_message": {
                "id": user_message.id,
                "content": user_message.content
            },
            "agent_response": {
                "id": response["message"]["id"],
                "content": response["message"]["content"],
                "actions": response["actions"]
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao processar resposta: {str(e)}")