# app/api/admin_api.py - NOVO: Controller para funcionalidades administrativas

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from app.db.database import get_db
from app.models.user import User
from app.models.agent import Agent, AgentType
from app.models.template import Template, TemplateDepartment
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message
from app.core.security import get_current_active_user
from app.services.agent_service import get_agent_service
from app.services.template_service import get_template_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

# =============================================================================
# 🔧 GESTÃO DE SISTEMA
# =============================================================================

@router.get("/system/health")
async def system_health_check(
    include_detailed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🔧 Verifica saúde do sistema do usuário
    """
    try:
        # Verificar componentes básicos
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user.id,
            "components": {}
        }
        
        # Verificar banco de dados
        try:
            db.execute("SELECT 1")
            health_status["components"]["database"] = "healthy"
        except Exception as e:
            health_status["components"]["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Verificar agentes do usuário
        try:
            agents_count = db.query(Agent).filter(
                Agent.user_id == current_user.id,
                Agent.is_active == True
            ).count()
            health_status["components"]["agents"] = {
                "status": "healthy",
                "active_count": agents_count
            }
        except Exception as e:
            health_status["components"]["agents"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Verificar templates
        try:
            templates_count = db.query(Template).filter(
                Template.user_id == current_user.id
            ).count()
            health_status["components"]["templates"] = {
                "status": "healthy", 
                "count": templates_count
            }
        except Exception as e:
            health_status["components"]["templates"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Verificar conversas ativas
        try:
            active_conversations = db.query(Conversation).filter(
                Conversation.user_id == current_user.id,
                Conversation.status == ConversationStatus.ACTIVE
            ).count()
            health_status["components"]["conversations"] = {
                "status": "healthy",
                "active_count": active_conversations
            }
        except Exception as e:
            health_status["components"]["conversations"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Detalhes adicionais se solicitado
        if include_detailed:
            # Verificar LLM
            try:
                from app.llm.smart_router import get_smart_router
                smart_router = get_smart_router()
                queue_status = await smart_router.get_queue_status()
                health_status["components"]["llm"] = {
                    "status": "healthy",
                    "queue_running": queue_status.get("running", False),
                    "pending_tasks": queue_status.get("pending_tasks", 0)
                }
            except Exception as e:
                health_status["components"]["llm"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
            
            # Verificar orquestração
            try:
                from app.orchestration import get_orchestrator
                orchestrator = get_orchestrator(db)
                health_status["components"]["orchestrator"] = "healthy"
            except Exception as e:
                health_status["components"]["orchestrator"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@router.get("/system/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📊 Estatísticas gerais do sistema do usuário
    """
    try:
        # Contar recursos
        agents_total = db.query(Agent).filter(Agent.user_id == current_user.id).count()
        agents_active = db.query(Agent).filter(
            Agent.user_id == current_user.id,
            Agent.is_active == True
        ).count()
        
        templates_total = db.query(Template).filter(Template.user_id == current_user.id).count()
        
        conversations_total = db.query(Conversation).filter(Conversation.user_id == current_user.id).count()
        conversations_active = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.status == ConversationStatus.ACTIVE
        ).count()
        
        messages_total = db.query(Message).join(Conversation).filter(
            Conversation.user_id == current_user.id
        ).count()
        
        # Distribuição por tipo de agente
        agent_types = db.query(
            Agent.type,
            db.func.count(Agent.id).label('count')
        ).filter(
            Agent.user_id == current_user.id
        ).group_by(Agent.type).all()
        
        agent_distribution = {
            agent_type.type.value: agent_type.count 
            for agent_type in agent_types
        }
        
        # Atividade recente (últimos 7 dias)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_conversations = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.created_at >= week_ago
        ).count()
        
        recent_messages = db.query(Message).join(Conversation).filter(
            Conversation.user_id == current_user.id,
            Message.created_at >= week_ago
        ).count()
        
        return {
            "user_id": current_user.id,
            "resources": {
                "agents": {
                    "total": agents_total,
                    "active": agents_active,
                    "inactive": agents_total - agents_active
                },
                "templates": {
                    "total": templates_total
                },
                "conversations": {
                    "total": conversations_total,
                    "active": conversations_active,
                    "archived": conversations_total - conversations_active
                },
                "messages": {
                    "total": messages_total
                }
            },
            "agent_distribution": agent_distribution,
            "recent_activity": {
                "conversations_7d": recent_conversations,
                "messages_7d": recent_messages
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter estatísticas: {str(e)}"
        )

# =============================================================================
# 🧹 LIMPEZA E MANUTENÇÃO
# =============================================================================

@router.post("/cleanup/conversations")
async def cleanup_conversations(
    archive_inactive_days: int = Body(30, description="Arquivar conversas inativas há X dias"),
    delete_archived_days: int = Body(90, description="Deletar conversas arquivadas há X dias"),
    dry_run: bool = Body(True, description="Apenas simular, não executar alterações"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🧹 Limpeza automática de conversas antigas
    """
    try:
        now = datetime.utcnow()
        archive_cutoff = now - timedelta(days=archive_inactive_days)
        delete_cutoff = now - timedelta(days=delete_archived_days)
        
        # Conversas inativas para arquivar
        conversations_to_archive = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.updated_at < archive_cutoff
        ).all()
        
        # Conversas arquivadas para deletar
        conversations_to_delete = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.status == ConversationStatus.ARCHIVED,
            Conversation.updated_at < delete_cutoff
        ).all()
        
        results = {
            "dry_run": dry_run,
            "conversations_to_archive": len(conversations_to_archive),
            "conversations_to_delete": len(conversations_to_delete),
            "archived_ids": [],
            "deleted_ids": []
        }
        
        if not dry_run:
            # Arquivar conversas inativas
            for conv in conversations_to_archive:
                conv.status = ConversationStatus.ARCHIVED
                conv.updated_at = now
                results["archived_ids"].append(conv.id)
            
            # Deletar conversas arquivadas antigas
            for conv in conversations_to_delete:
                results["deleted_ids"].append(conv.id)
                db.delete(conv)
            
            db.commit()
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na limpeza: {str(e)}"
        )

@router.post("/cleanup/agents")
async def cleanup_agents(
    remove_unused_days: int = Body(60, description="Remover agentes não usados há X dias"),
    dry_run: bool = Body(True, description="Apenas simular, não executar alterações"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🧹 Limpeza de agentes não utilizados
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=remove_unused_days)
        
        # Encontrar agentes sem conversas recentes
        agents_with_recent_activity = db.query(Agent.id).join(Conversation).filter(
            Agent.user_id == current_user.id,
            Conversation.created_at >= cutoff_date
        ).distinct().all()
        
        active_agent_ids = [agent.id for agent in agents_with_recent_activity]
        
        # Agentes sem atividade recente
        unused_agents = db.query(Agent).filter(
            Agent.user_id == current_user.id,
            Agent.is_active == True,
            ~Agent.id.in_(active_agent_ids)
        ).all()
        
        results = {
            "dry_run": dry_run,
            "unused_agents_found": len(unused_agents),
            "deactivated_ids": []
        }
        
        if not dry_run:
            for agent in unused_agents:
                agent.is_active = False
                agent.updated_at = datetime.utcnow()
                results["deactivated_ids"].append(agent.id)
            
            db.commit()
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na limpeza de agentes: {str(e)}"
        )

# =============================================================================
# 📤 EXPORTAÇÃO E BACKUP
# =============================================================================

@router.get("/export/conversations")
async def export_conversations(
    format: str = Query("json", regex="^(json|csv)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_messages: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📤 Exporta conversas do usuário
    """
    try:
        # Definir período se não especificado
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=365)  # Último ano
        
        # Buscar conversas
        conversations = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date
        ).all()
        
        export_data = []
        
        for conv in conversations:
            # Obter agente
            agent = db.query(Agent).filter(Agent.id == conv.agent_id).first()
            
            conv_data = {
                "conversation_id": conv.id,
                "title": conv.title,
                "status": conv.status.value,
                "agent_name": agent.name if agent else "Agente removido",
                "agent_type": agent.type.value if agent else "unknown",
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "metadata": conv.meta_data
            }
            
            # Incluir mensagens se solicitado
            if include_messages:
                messages = db.query(Message).filter(
                    Message.conversation_id == conv.id
                ).order_by(Message.created_at).all()
                
                conv_data["messages"] = [
                    {
                        "message_id": msg.id,
                        "role": msg.role.value,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                        "metadata": msg.meta_data
                    }
                    for msg in messages
                ]
            
            export_data.append(conv_data)
        
        if format == "csv":
            # Para CSV, achatar a estrutura
            import csv
            import io
            
            output = io.StringIO()
            
            if export_data:
                # Cabeçalhos básicos da conversa
                fieldnames = ["conversation_id", "title", "status", "agent_name", "agent_type", "created_at", "updated_at"]
                
                if include_messages:
                    fieldnames.extend(["message_role", "message_content", "message_created_at"])
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for conv in export_data:
                    if include_messages and "messages" in conv:
                        for msg in conv["messages"]:
                            row = {k: v for k, v in conv.items() if k != "messages"}
                            row.update({
                                "message_role": msg["role"],
                                "message_content": msg["content"],
                                "message_created_at": msg["created_at"]
                            })
                            writer.writerow(row)
                    else:
                        writer.writerow({k: v for k, v in conv.items() if k != "messages"})
            
            return {
                "format": "csv",
                "content": output.getvalue(),
                "filename": f"conversations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        
        else:  # JSON
            return {
                "format": "json",
                "export_info": {
                    "user_id": current_user.id,
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    },
                    "total_conversations": len(conversations),
                    "exported_at": datetime.utcnow().isoformat()
                },
                "conversations": export_data
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na exportação: {str(e)}"
        )

@router.get("/export/agents")
async def export_agents_config(
    include_templates: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📤 Exporta configuração dos agentes
    """
    try:
        # Buscar agentes
        agents = db.query(Agent).filter(Agent.user_id == current_user.id).all()
        
        export_data = {
            "user_id": current_user.id,
            "exported_at": datetime.utcnow().isoformat(),
            "agents": []
        }
        
        for agent in agents:
            agent_data = {
                "name": agent.name,
                "description": agent.description,
                "type": agent.type.value,
                "configuration": agent.configuration,
                "is_active": agent.is_active,
                "template_id": agent.template_id,
                "created_at": agent.created_at.isoformat()
            }
            
            # Incluir informações do template se solicitado
            if include_templates and agent.template:
                agent_data["template_info"] = {
                    "name": agent.template.name,
                    "description": agent.template.description,
                    "department": agent.template.department.value,
                    "prompt_template": agent.template.prompt_template,
                    "tools_config": agent.template.tools_config,
                    "llm_config": agent.template.llm_config
                }
            
            export_data["agents"].append(agent_data)
        
        return export_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na exportação de agentes: {str(e)}"
        )

# =============================================================================
# 🔄 OPERAÇÕES EM LOTE
# =============================================================================

@router.post("/bulk/activate-agents")
async def bulk_activate_agents(
    agent_ids: List[str] = Body(..., description="Lista de IDs dos agentes"),
    activate: bool = Body(True, description="True para ativar, False para desativar"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🔄 Ativa/desativa múltiplos agentes
    """
    try:
        # Verificar propriedade dos agentes
        agents = db.query(Agent).filter(
            Agent.id.in_(agent_ids),
            Agent.user_id == current_user.id
        ).all()
        
        if len(agents) != len(agent_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Um ou mais agentes não foram encontrados"
            )
        
        # Atualizar status
        updated_agents = []
        for agent in agents:
            agent.is_active = activate
            agent.updated_at = datetime.utcnow()
            updated_agents.append({
                "id": agent.id,
                "name": agent.name,
                "is_active": agent.is_active
            })
        
        db.commit()
        
        return {
            "success": True,
            "action": "activated" if activate else "deactivated",
            "total_updated": len(updated_agents),
            "agents": updated_agents
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na operação em lote: {str(e)}"
        )