# app/api/conversations_api.py - Reorganizado: Foco na gestão de conversas

from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.user import User
from app.models.agent import Agent
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.core.security import get_current_active_user
from app.schemas.conversation import (
    ConversationCreate, ConversationUpdate, 
    Conversation as ConversationSchema
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# =============================================================================
# 💬 CRIAÇÃO E GESTÃO DE CONVERSAS
# =============================================================================

@router.post("/", response_model=ConversationSchema)
async def create_conversation(
    conversation_data: ConversationCreate,
    auto_start: bool = Query(False, description="Iniciar conversa automaticamente com mensagem de boas-vindas"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    💬 Cria uma nova conversa com um agente
    
    Fluxo:
    1. Valida o agente selecionado
    2. Cria a conversa
    3. Opcionalmente envia mensagem de boas-vindas
    """
    try:
        # Verificar se o agente existe e pertence ao usuário
        agent = db.query(Agent).filter(
            Agent.id == conversation_data.agent_id,
            Agent.user_id == current_user.id,
            Agent.is_active == True
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agente não encontrado ou inativo"
            )
        
        # Criar título automático se não fornecido
        if not conversation_data.title:
            conversation_data.title = f"Conversa com {agent.name} - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        # Criar a conversa
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=conversation_data.title,
            user_id=current_user.id,
            agent_id=conversation_data.agent_id,
            status=ConversationStatus.ACTIVE,
            meta_data=conversation_data.metadata or {}
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        # Iniciar conversa automaticamente se solicitado
        if auto_start:
            welcome_message = Message(
                id=str(uuid.uuid4()),
                conversation_id=conversation.id,
                role=MessageRole.AGENT,
                content=f"Olá! Sou o {agent.name}, especializado em {agent.type.value}. Como posso ajudar você hoje?",
                meta_data={"auto_generated": True, "welcome": True}
            )
            
            db.add(welcome_message)
            db.commit()
        
        return ConversationSchema(
            id=conversation.id,
            title=conversation.title,
            user_id=conversation.user_id,
            agent_id=conversation.agent_id,
            status=conversation.status,
            metadata=conversation.meta_data,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar conversa: {str(e)}"
        )

@router.get("/", response_model=Dict[str, Any])
async def list_conversations(
    status_filter: Optional[ConversationStatus] = Query(None, alias="status"),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("updated_at", regex="^(created_at|updated_at|title)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    include_preview: bool = Query(True, description="Incluir preview da última mensagem"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📋 Lista conversas do usuário com filtros e ordenação
    """
    try:
        # Construir query
        query = db.query(Conversation).filter(
            Conversation.user_id == current_user.id
        )
        
        # Aplicar filtros
        if status_filter:
            query = query.filter(Conversation.status == status_filter)
        
        if agent_id:
            query = query.filter(Conversation.agent_id == agent_id)
        
        # Aplicar ordenação
        if sort_by == "created_at":
            order_column = Conversation.created_at
        elif sort_by == "title":
            order_column = Conversation.title
        else:  # updated_at (padrão)
            order_column = Conversation.updated_at
        
        if sort_order == "asc":
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())
        
        # Obter total e aplicar paginação
        total = query.count()
        conversations = query.offset(offset).limit(limit).all()
        
        # Preparar resposta
        items = []
        for conv in conversations:
            # Obter informações do agente
            agent = db.query(Agent).filter(Agent.id == conv.agent_id).first()
            
            # Contar mensagens
            message_count = db.query(Message).filter(
                Message.conversation_id == conv.id
            ).count()
            
            # Preparar item da conversa
            conv_item = {
                "id": conv.id,
                "title": conv.title,
                "status": conv.status.value,
                "agent": {
                    "id": agent.id if agent else None,
                    "name": agent.name if agent else "Agente removido",
                    "type": agent.type.value if agent else "unknown"
                },
                "message_count": message_count,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "metadata": conv.meta_data
            }
            
            # Incluir preview da última mensagem se solicitado
            if include_preview:
                last_message = db.query(Message).filter(
                    Message.conversation_id == conv.id
                ).order_by(Message.created_at.desc()).first()
                
                if last_message:
                    conv_item["last_message"] = {
                        "content": last_message.content[:150] + "..." if len(last_message.content) > 150 else last_message.content,
                        "role": last_message.role.value,
                        "created_at": last_message.created_at.isoformat()
                    }
                else:
                    conv_item["last_message"] = None
            
            items.append(conv_item)
        
        return {
            "conversations": {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset
            },
            "filters": {
                "status": status_filter.value if status_filter else None,
                "agent_id": agent_id,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar conversas: {str(e)}"
        )

@router.get("/{conversation_id}", response_model=ConversationSchema)
async def get_conversation(
    conversation_id: str,
    include_agent_info: bool = Query(True),
    include_message_count: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🔍 Obtém detalhes de uma conversa específica
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa não encontrada"
            )
        
        # Preparar resposta base
        response_data = ConversationSchema(
            id=conversation.id,
            title=conversation.title,
            user_id=conversation.user_id,
            agent_id=conversation.agent_id,
            status=conversation.status,
            metadata=conversation.meta_data,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
        # Incluir informações do agente se solicitado
        if include_agent_info:
            agent = db.query(Agent).filter(Agent.id == conversation.agent_id).first()
            if agent:
                response_data.agent_info = {
                    "name": agent.name,
                    "type": agent.type.value,
                    "description": agent.description,
                    "is_active": agent.is_active
                }
        
        # Incluir contagem de mensagens se solicitado
        if include_message_count:
            total_messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).count()
            
            user_messages = db.query(Message).filter(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.HUMAN
            ).count()
            
            agent_messages = db.query(Message).filter(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.AGENT
            ).count()
            
            response_data.message_stats = {
                "total": total_messages,
                "user_messages": user_messages,
                "agent_messages": agent_messages
            }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter conversa: {str(e)}"
        )

@router.put("/{conversation_id}", response_model=ConversationSchema)
async def update_conversation(
    conversation_id: str,
    conversation_data: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ✏️ Atualiza uma conversa existente
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa não encontrada"
            )
        
        # Atualizar campos
        if conversation_data.title is not None:
            conversation.title = conversation_data.title
        
        if conversation_data.status is not None:
            conversation.status = conversation_data.status
        
        if conversation_data.metadata is not None:
            conversation.meta_data = conversation_data.metadata
        
        # Atualizar timestamp
        conversation.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(conversation)
        
        return ConversationSchema(
            id=conversation.id,
            title=conversation.title,
            user_id=conversation.user_id,
            agent_id=conversation.agent_id,
            status=conversation.status,
            metadata=conversation.meta_data,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar conversa: {str(e)}"
        )

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    archive_instead: bool = Query(True, description="Se True, arquiva em vez de deletar"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🗑️ Remove ou arquiva uma conversa
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa não encontrada"
            )
        
        if archive_instead:
            # Arquivar em vez de deletar
            conversation.status = ConversationStatus.ARCHIVED
            conversation.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                "success": True,
                "action": "archived",
                "conversation_id": conversation_id,
                "message": "Conversa arquivada com sucesso"
            }
        else:
            # Deletar completamente (cascade delete cuidará das mensagens)
            db.delete(conversation)
            db.commit()
            
            return {
                "success": True,
                "action": "deleted",
                "conversation_id": conversation_id,
                "message": "Conversa removida com sucesso"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao remover conversa: {str(e)}"
        )

# =============================================================================
# 🔄 OPERAÇÕES ESPECIAIS
# =============================================================================

@router.post("/{conversation_id}/activate")
async def activate_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ✅ Ativa uma conversa arquivada
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa não encontrada"
            )
        
        conversation.status = ConversationStatus.ACTIVE
        conversation.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "status": "active",
            "message": "Conversa ativada com sucesso"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao ativar conversa: {str(e)}"
        )

@router.post("/{conversation_id}/duplicate")
async def duplicate_conversation(
    conversation_id: str,
    new_title: Optional[str] = Body(None, embed=True),
    include_messages: bool = Body(False, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📋 Duplica uma conversa existente
    """
    try:
        # Verificar conversa original
        original_conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not original_conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa não encontrada"
            )
        
        # Criar nova conversa
        new_conversation = Conversation(
            id=str(uuid.uuid4()),
            title=new_title or f"{original_conversation.title} (Cópia)",
            user_id=current_user.id,
            agent_id=original_conversation.agent_id,
            status=ConversationStatus.ACTIVE,
            meta_data=original_conversation.meta_data.copy() if original_conversation.meta_data else {}
        )
        
        db.add(new_conversation)
        db.commit()
        db.refresh(new_conversation)
        
        # Copiar mensagens se solicitado
        if include_messages:
            original_messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).all()
            
            for orig_msg in original_messages:
                new_message = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=new_conversation.id,
                    role=orig_msg.role,
                    content=orig_msg.content,
                    meta_data=orig_msg.meta_data.copy() if orig_msg.meta_data else {}
                )
                db.add(new_message)
            
            db.commit()
        
        return {
            "success": True,
            "original_conversation_id": conversation_id,
            "new_conversation": {
                "id": new_conversation.id,
                "title": new_conversation.title,
                "created_at": new_conversation.created_at.isoformat()
            },
            "messages_copied": include_messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao duplicar conversa: {str(e)}"
        )

# =============================================================================
# 📊 ESTATÍSTICAS E RESUMOS
# =============================================================================

@router.get("/stats/summary")
async def get_conversations_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📊 Obtém resumo estatístico das conversas do usuário
    """
    try:
        # Período de análise
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Conversas totais
        total_conversations = db.query(Conversation).filter(
            Conversation.user_id == current_user.id
        ).count()
        
        # Conversas no período
        recent_conversations = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.created_at >= start_date
        ).count()
        
        # Conversas ativas
        active_conversations = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.status == ConversationStatus.ACTIVE
        ).count()
        
        # Conversas por agente
        conversations_by_agent = db.query(
            Agent.name,
            Agent.type,
            db.func.count(Conversation.id).label('conversation_count')
        ).join(
            Conversation, Agent.id == Conversation.agent_id
        ).filter(
            Conversation.user_id == current_user.id
        ).group_by(Agent.id, Agent.name, Agent.type).all()
        
        # Total de mensagens
        total_messages = db.query(Message).join(Conversation).filter(
            Conversation.user_id == current_user.id
        ).count()
        
        return {
            "period_days": days,
            "total_conversations": total_conversations,
            "recent_conversations": recent_conversations,
            "active_conversations": active_conversations,
            "archived_conversations": total_conversations - active_conversations,
            "total_messages": total_messages,
            "conversations_by_agent": [
                {
                    "agent_name": agent.name,
                    "agent_type": agent.type.value,
                    "conversation_count": agent.conversation_count
                }
                for agent in conversations_by_agent
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter resumo: {str(e)}"
        )