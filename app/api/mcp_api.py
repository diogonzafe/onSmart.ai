# app/api/mcp_api.py
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional

from app.db.database import get_db
from app.models.user import User
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.core.security import get_current_active_user
from app.core.mcp import get_mcp_formatter, get_mcp_processor

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

@router.get("/context/{conversation_id}")
async def get_mcp_context(
    conversation_id: str,
    include_tools: bool = True,
    max_messages: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtém o contexto MCP formatado para uma conversa.
    Útil para debug e desenvolvimento.
    """
    # Verificar acesso à conversa
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Obter o agente da conversa
    agent = db.query(Agent).filter(Agent.id == conversation.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Formatar o contexto
    formatter = get_mcp_formatter()
    context = formatter.format_conversation_context(
        db=db,
        agent=agent,
        conversation=conversation,
        max_messages=max_messages,
        include_tools=include_tools
    )
    
    return context

@router.post("/process-response")
async def process_mcp_response(
    response: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user)
):
    """
    Processa uma resposta no formato MCP.
    Extrai ações, valida e filtra o conteúdo.
    """
    processor = get_mcp_processor()
    result = processor.process_response(response)
    
    return result

@router.post("/send-message/{conversation_id}")
async def send_message_with_mcp(
    conversation_id: str,
    content: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Envia uma mensagem usando o protocolo MCP.
    Retorna o contexto formatado e a mensagem armazenada.
    """
    # Verificar acesso à conversa
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Obter o agente da conversa
    agent = db.query(Agent).filter(Agent.id == conversation.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Criar a mensagem
    message = Message(
        conversation_id=conversation_id,
        role=MessageRole.HUMAN,
        content=content
    )
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    # Formatar o contexto MCP com a nova mensagem
    formatter = get_mcp_formatter()
    context = formatter.format_conversation_context(
        db=db,
        agent=agent,
        conversation=conversation
    )
    
    return {
        "message": {
            "id": message.id,
            "content": message.content,
            "role": message.role.value,
            "created_at": message.created_at
        },
        "mcp_context": context
    }