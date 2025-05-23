# app/api/messages_api.py - NOVO: Controller dedicado para mensagens

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.models.agent import Agent
from app.core.security import get_current_active_user
from app.orchestration import get_orchestrator
from app.schemas.message import SendMessage

router = APIRouter(prefix="/api/messages", tags=["messages"])

# =============================================================================
# 📨 ENVIO DE MENSAGENS (Fluxo principal)
# =============================================================================

@router.post("/send")
async def send_message(
    conversation_id: str = Body(..., embed=True),
    content: str = Body(..., embed=True),
    metadata: Optional[Dict[str, Any]] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🎯 ENDPOINT PRINCIPAL - Envia mensagem e orquestra resposta via supervisor
    
    Este é o endpoint principal que o frontend deve usar para enviar mensagens.
    O sistema automaticamente:
    1. Valida a conversa e permissões
    2. Registra a mensagem do usuário
    3. Orquestra via supervisor para encontrar o agente adequado
    4. Retorna a resposta processada
    """
    try:
        # Validar conversa e permissões
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.status == ConversationStatus.ACTIVE
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa não encontrada ou inativa"
            )
        
        # Registrar mensagem do usuário
        user_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=MessageRole.HUMAN,
            content=content,
            meta_data=metadata or {}
        )
        
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        
        # Orquestrar resposta via supervisor
        orchestrator = get_orchestrator(db)
        
        response = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message=content,
            metadata=metadata
        )
        
        # Atualizar timestamp da conversa
        conversation.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message_id": user_message.id,
            "user_message": {
                "id": user_message.id,
                "content": user_message.content,
                "role": user_message.role.value,
                "created_at": user_message.created_at.isoformat()
            },
            "agent_response": {
                "content": response.get("response", ""),
                "agents_involved": response.get("agents_involved", []),
                "processing_time": response.get("processing_time", 0),
                "success": response.get("success", False)
            },
            "conversation_updated": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar mensagem: {str(e)}"
        )

# =============================================================================
# 📜 HISTÓRICO DE MENSAGENS
# =============================================================================

@router.get("/conversation/{conversation_id}")
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_metadata: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📜 Obtém histórico de mensagens de uma conversa
    """
    # Verificar acesso à conversa
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa não encontrada"
        )
    
    # Buscar mensagens
    query = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at)
    
    total = query.count()
    messages = query.offset(offset).limit(limit).all()
    
    # Formatar resposta
    items = []
    for msg in messages:
        message_data = {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role.value,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        }
        
        if include_metadata and msg.meta_data:
            message_data["metadata"] = msg.meta_data
            
        items.append(message_data)
    
    return {
        "conversation_id": conversation_id,
        "messages": {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    }

# =============================================================================
# 🔄 OPERAÇÕES ESPECIAIS
# =============================================================================

@router.post("/regenerate")
async def regenerate_last_response(
    conversation_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🔄 Regenera a última resposta do agente
    """
    try:
        # Verificar conversa
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa não encontrada"
            )
        
        # Encontrar última mensagem do usuário
        last_user_message = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.role == MessageRole.HUMAN
        ).order_by(Message.created_at.desc()).first()
        
        if not last_user_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhuma mensagem do usuário encontrada"
            )
        
        # Orquestrar nova resposta
        orchestrator = get_orchestrator(db)
        
        response = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message=last_user_message.content,
            metadata={"regenerated": True}
        )
        
        return {
            "success": True,
            "regenerated": True,
            "original_message": last_user_message.content,
            "agent_response": {
                "content": response.get("response", ""),
                "agents_involved": response.get("agents_involved", []),
                "processing_time": response.get("processing_time", 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao regenerar resposta: {str(e)}"
        )

@router.post("/continue")
async def continue_conversation(
    conversation_id: str = Body(..., embed=True),
    prompt: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ➡️ Continua uma conversa interrompida
    """
    try:
        from app.services.conversation_service import ConversationService
        conversation_service = ConversationService(db)
        
        result = await conversation_service.resume_conversation(
            conversation_id=conversation_id,
            message=prompt
        )
        
        return {
            "success": True,
            "continued": True,
            "status": result.get("status"),
            "response": result.get("response") if result.get("message_processed") else None
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao continuar conversa: {str(e)}"
        )

# =============================================================================
# 📊 FEEDBACK E AVALIAÇÃO
# =============================================================================

@router.post("/feedback")
async def submit_message_feedback(
    message_id: str = Body(..., embed=True),
    rating: int = Body(..., ge=1, le=5, embed=True),
    feedback_text: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ⭐ Envia feedback sobre uma mensagem específica
    """
    from app.models.metrics import UserFeedback
    
    # Verificar se a mensagem existe e o usuário tem acesso
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensagem não encontrada"
        )
    
    conversation = db.query(Conversation).filter(
        Conversation.id == message.conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado a esta mensagem"
        )
    
    # Verificar se já existe feedback
    existing_feedback = db.query(UserFeedback).filter(
        UserFeedback.message_id == message_id
    ).first()
    
    if existing_feedback:
        # Atualizar feedback existente
        existing_feedback.rating = rating
        existing_feedback.feedback_text = feedback_text
        db.commit()
        
        return {
            "success": True,
            "updated": True,
            "feedback_id": existing_feedback.id
        }
    
    # Criar novo feedback
    feedback = UserFeedback(
        id=str(uuid.uuid4()),
        message_id=message_id,
        rating=rating,
        feedback_text=feedback_text
    )
    
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    
    return {
        "success": True,
        "created": True,
        "feedback_id": feedback.id
    }

# =============================================================================
# 🔍 BUSCA E FILTROS
# =============================================================================

@router.get("/search")
async def search_messages(
    query: str = Query(..., min_length=3),
    conversation_id: Optional[str] = Query(None),
    role: Optional[MessageRole] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🔍 Busca mensagens por conteúdo
    """
    # Construir query base
    base_query = db.query(Message).join(Conversation).filter(
        Conversation.user_id == current_user.id,
        Message.content.ilike(f"%{query}%")
    )
    
    # Aplicar filtros
    if conversation_id:
        base_query = base_query.filter(Message.conversation_id == conversation_id)
    
    if role:
        base_query = base_query.filter(Message.role == role)
    
    # Executar busca
    messages = base_query.order_by(
        Message.created_at.desc()
    ).limit(limit).all()
    
    # Formatar resultados
    results = []
    for msg in messages:
        # Buscar informações da conversa
        conv = db.query(Conversation).filter(Conversation.id == msg.conversation_id).first()
        
        results.append({
            "message_id": msg.id,
            "content": msg.content,
            "role": msg.role.value,
            "created_at": msg.created_at.isoformat(),
            "conversation": {
                "id": conv.id,
                "title": conv.title
            }
        })
    
    return {
        "query": query,
        "results": results,
        "total_found": len(results)
    }