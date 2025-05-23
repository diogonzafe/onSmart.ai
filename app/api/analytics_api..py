# app/api/analytics_api.py - NOVO: Analytics centralizado (renomeado de metrics_api.py)

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

from app.db.database import get_db
from app.models.user import User
from app.models.agent import Agent, AgentType
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.models.metrics import AgentMetrics, UserFeedback
from app.core.security import get_current_active_user
from app.schemas.metrics import (
    AgentMetricsCreate, UserFeedbackCreate, 
    AgentPerformanceSummary, UserFeedback as UserFeedbackSchema
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# =============================================================================
# 📊 DASHBOARD PRINCIPAL
# =============================================================================

@router.get("/dashboard")
async def get_analytics_dashboard(
    period: str = Query("month", regex="^(day|week|month|quarter|year)$"),
    include_trends: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📊 Dashboard principal com todas as métricas importantes
    """
    try:
        # Definir período
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
            previous_period_start = start_date - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
            previous_period_start = start_date - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
            previous_period_start = start_date - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
            previous_period_start = start_date - timedelta(days=90)
        else:  # year
            start_date = now - timedelta(days=365)
            previous_period_start = start_date - timedelta(days=365)
        
        # Métricas de conversas
        conversations_current = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.created_at >= start_date
        ).count()
        
        conversations_previous = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.created_at >= previous_period_start,
            Conversation.created_at < start_date
        ).count() if include_trends else 0
        
        # Métricas de mensagens
        messages_current = db.query(Message).join(Conversation).filter(
            Conversation.user_id == current_user.id,
            Message.created_at >= start_date
        ).count()
        
        messages_previous = db.query(Message).join(Conversation).filter(
            Conversation.user_id == current_user.id,
            Message.created_at >= previous_period_start,
            Message.created_at < start_date
        ).count() if include_trends else 0
        
        # Métricas de agentes
        active_agents = db.query(Agent).filter(
            Agent.user_id == current_user.id,
            Agent.is_active == True
        ).count()
        
        # Feedback médio
        avg_feedback = db.query(db.func.avg(UserFeedback.rating)).join(
            Message
        ).join(Conversation).filter(
            Conversation.user_id == current_user.id,
            UserFeedback.created_at >= start_date
        ).scalar() or 0
        
        # Top agentes por uso
        top_agents = db.query(
            Agent.id,
            Agent.name,
            Agent.type,
            db.func.count(Conversation.id).label('conversation_count')
        ).join(
            Conversation, Agent.id == Conversation.agent_id
        ).filter(
            Conversation.user_id == current_user.id,
            Conversation.created_at >= start_date
        ).group_by(Agent.id, Agent.name, Agent.type).order_by(
            db.func.count(Conversation.id).desc()
        ).limit(5).all()
        
        # Atividade por dia (se incluir trends)
        daily_activity = []
        if include_trends:
            for i in range(7):  # Últimos 7 dias
                day_start = now - timedelta(days=i+1)
                day_end = now - timedelta(days=i)
                
                day_messages = db.query(Message).join(Conversation).filter(
                    Conversation.user_id == current_user.id,
                    Message.created_at >= day_start,
                    Message.created_at < day_end
                ).count()
                
                daily_activity.append({
                    "date": day_start.strftime("%Y-%m-%d"),
                    "messages": day_messages
                })
        
        # Calcular tendências
        def calculate_trend(current, previous):
            if previous == 0:
                return 0 if current == 0 else 100
            return round(((current - previous) / previous) * 100, 1)
        
        return {
            "period": period,
            "overview": {
                "conversations": {
                    "current": conversations_current,
                    "previous": conversations_previous,
                    "trend": calculate_trend(conversations_current, conversations_previous) if include_trends else None
                },
                "messages": {
                    "current": messages_current,
                    "previous": messages_previous,
                    "trend": calculate_trend(messages_current, messages_previous) if include_trends else None
                },
                "active_agents": active_agents,
                "avg_feedback": round(avg_feedback, 1)
            },
            "top_agents": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "type": agent.type.value,
                    "conversations": agent.conversation_count
                }
                for agent in top_agents
            ],
            "daily_activity": daily_activity if include_trends else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter dashboard: {str(e)}"
        )

# =============================================================================
# 🤖 ANALYTICS DE AGENTES
# =============================================================================

@router.get("/agents/{agent_id}", response_model=AgentPerformanceSummary)
async def get_agent_analytics(
    agent_id: str,
    period: str = Query("month", regex="^(day|week|month|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🤖 Análise detalhada de performance de um agente
    """
    try:
        # Verificar acesso ao agente
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.user_id == current_user.id
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agente não encontrado"
            )
        
        # Definir período
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # Buscar métricas
        metrics = db.query(AgentMetrics).filter(
            AgentMetrics.agent_id == agent_id,
            AgentMetrics.created_at >= start_date
        ).all()
        
        # Calcular estatísticas
        total_interactions = len(metrics)
        avg_response_time = sum(m.response_time for m in metrics) / total_interactions if total_interactions > 0 else 0
        
        # Contar mensagens e conversas
        conversations = db.query(Conversation).filter(
            Conversation.agent_id == agent_id,
            Conversation.user_id == current_user.id,
            Conversation.created_at >= start_date
        ).all()
        
        conversation_count = len(conversations)
        conversation_ids = [c.id for c in conversations]
        
        messages = db.query(Message).filter(
            Message.conversation_id.in_(conversation_ids),
            Message.role == MessageRole.AGENT
        ).all()
        
        message_count = len(messages)
        
        # Análise de ferramentas usadas
        tools_usage = {}
        for metric in metrics:
            if metric.tools_used and isinstance(metric.tools_used, dict):
                for tool, count in metric.tools_used.items():
                    tools_usage[tool] = tools_usage.get(tool, 0) + count
        
        # Feedback médio
        feedbacks = db.query(UserFeedback).filter(
            UserFeedback.message_id.in_([m.id for m in messages]),
            UserFeedback.created_at >= start_date
        ).all()
        
        avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks) if feedbacks else None
        
        return AgentPerformanceSummary(
            agent_id=agent_id,
            agent_name=agent.name,
            avg_response_time=avg_response_time,
            total_conversations=conversation_count,
            total_messages=message_count,
            avg_rating=avg_rating,
            tools_usage=tools_usage,
            period_start=start_date,
            period_end=now
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter analytics do agente: {str(e)}"
        )

@router.get("/agents/compare")
async def compare_agents(
    agent_ids: List[str] = Query(..., description="Lista de IDs dos agentes para comparar"),
    period: str = Query("month", regex="^(day|week|month|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ⚖️ Compara performance entre múltiplos agentes
    """
    try:
        if len(agent_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pelo menos 2 agentes são necessários para comparação"
            )
        
        # Verificar acesso aos agentes
        agents = db.query(Agent).filter(
            Agent.id.in_(agent_ids),
            Agent.user_id == current_user.id
        ).all()
        
        if len(agents) != len(agent_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Um ou mais agentes não foram encontrados"
            )
        
        # Definir período
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # Comparar agentes
        comparison_data = []
        
        for agent in agents:
            # Buscar métricas do agente
            metrics = db.query(AgentMetrics).filter(
                AgentMetrics.agent_id == agent.id,
                AgentMetrics.created_at >= start_date
            ).all()
            
            # Contar conversas
            conversations = db.query(Conversation).filter(
                Conversation.agent_id == agent.id,
                Conversation.user_id == current_user.id,
                Conversation.created_at >= start_date
            ).count()
            
            # Contar mensagens
            messages = db.query(Message).join(Conversation).filter(
                Conversation.agent_id == agent.id,
                Conversation.user_id == current_user.id,
                Message.role == MessageRole.AGENT,
                Message.created_at >= start_date
            ).count()
            
            # Calcular tempo médio de resposta
            avg_response_time = sum(m.response_time for m in metrics) / len(metrics) if metrics else 0
            
            # Feedback médio
            feedbacks = db.query(UserFeedback).join(Message).join(Conversation).filter(
                Conversation.agent_id == agent.id,
                Conversation.user_id == current_user.id,
                UserFeedback.created_at >= start_date
            ).all()
            
            avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks) if feedbacks else None
            
            comparison_data.append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "agent_type": agent.type.value,
                "conversations": conversations,
                "messages": messages,
                "avg_response_time": round(avg_response_time, 2),
                "avg_rating": round(avg_rating, 1) if avg_rating else None,
                "interactions": len(metrics)
            })
        
        return {
            "period": period,
            "agents_compared": len(agents),
            "comparison": comparison_data,
            "summary": {
                "most_active": max(comparison_data, key=lambda x: x["conversations"]),
                "fastest_response": min(comparison_data, key=lambda x: x["avg_response_time"]),
                "highest_rated": max(comparison_data, key=lambda x: x["avg_rating"] or 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao comparar agentes: {str(e)}"
        )

# =============================================================================
# ⭐ FEEDBACK E AVALIAÇÕES
# =============================================================================

@router.post("/feedback", response_model=UserFeedbackSchema)
async def create_feedback(
    feedback_data: UserFeedbackCreate,
    message_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ⭐ Cria feedback para uma mensagem específica
    """
    try:
        # Verificar acesso à mensagem
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
            existing_feedback.rating = feedback_data.rating
            existing_feedback.feedback_text = feedback_data.feedback_text
            db.commit()
            db.refresh(existing_feedback)
            
            return UserFeedbackSchema(
                id=existing_feedback.id,
                message_id=existing_feedback.message_id,
                rating=existing_feedback.rating,
                feedback_text=existing_feedback.feedback_text,
                created_at=existing_feedback.created_at
            )
        
        # Criar novo feedback
        feedback = UserFeedback(
            id=str(uuid.uuid4()),
            message_id=message_id,
            rating=feedback_data.rating,
            feedback_text=feedback_data.feedback_text
        )
        
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        return UserFeedbackSchema(
            id=feedback.id,
            message_id=feedback.message_id,
            rating=feedback.rating,
            feedback_text=feedback.feedback_text,
            created_at=feedback.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar feedback: {str(e)}"
        )

@router.get("/feedback/summary")
async def get_feedback_summary(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    agent_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📊 Resumo de feedback recebido
    """
    try:
        # Definir período
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # Construir query base
        query = db.query(UserFeedback).join(Message).join(Conversation).filter(
            Conversation.user_id == current_user.id,
            UserFeedback.created_at >= start_date
        )
        
        # Filtrar por agente se especificado
        if agent_id:
            query = query.filter(Conversation.agent_id == agent_id)
        
        feedbacks = query.all()
        
        if not feedbacks:
            return {
                "period": period,
                "total_feedback": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "recent_feedback": []
            }
        
        # Calcular estatísticas
        total_feedback = len(feedbacks)
        average_rating = sum(f.rating for f in feedbacks) / total_feedback
        
        # Distribuição de ratings
        rating_distribution = {}
        for rating in range(1, 6):
            count = sum(1 for f in feedbacks if f.rating == rating)
            rating_distribution[str(rating)] = count
        
        # Feedback recente
        recent_feedback = []
        for feedback in sorted(feedbacks, key=lambda x: x.created_at, reverse=True)[:5]:
            # Obter informações da mensagem e conversa
            message = db.query(Message).filter(Message.id == feedback.message_id).first()
            conversation = db.query(Conversation).filter(Conversation.id == message.conversation_id).first()
            agent = db.query(Agent).filter(Agent.id == conversation.agent_id).first()
            
            recent_feedback.append({
                "rating": feedback.rating,
                "feedback_text": feedback.feedback_text,
                "created_at": feedback.created_at.isoformat(),
                "agent_name": agent.name if agent else "Agente removido",
                "conversation_title": conversation.title
            })
        
        return {
            "period": period,
            "total_feedback": total_feedback,
            "average_rating": round(average_rating, 1),
            "rating_distribution": rating_distribution,
            "recent_feedback": recent_feedback
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter resumo de feedback: {str(e)}"
        )

# =============================================================================
# 📈 RELATÓRIOS AVANÇADOS
# =============================================================================

@router.get("/reports/usage")
async def get_usage_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    group_by: str = Query("day", regex="^(hour|day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📈 Relatório detalhado de uso do sistema
    """
    try:
        # Definir período padrão se não especificado
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Buscar dados de uso
        conversations = db.query(Conversation).filter(
            Conversation.user_id == current_user.id,
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date
        ).all()
        
        messages = db.query(Message).join(Conversation).filter(
            Conversation.user_id == current_user.id,
            Message.created_at >= start_date,
            Message.created_at <= end_date
        ).all()
        
        # Agrupar dados por período
        usage_data = {}
        
        for conversation in conversations:
            if group_by == "hour":
                key = conversation.created_at.strftime("%Y-%m-%d %H:00")
            elif group_by == "day":
                key = conversation.created_at.strftime("%Y-%m-%d")
            elif group_by == "week":
                key = conversation.created_at.strftime("%Y-W%U")
            else:  # month
                key = conversation.created_at.strftime("%Y-%m")
            
            if key not in usage_data:
                usage_data[key] = {"conversations": 0, "messages": 0}
            usage_data[key]["conversations"] += 1
        
        for message in messages:
            if group_by == "hour":
                key = message.created_at.strftime("%Y-%m-%d %H:00")
            elif group_by == "day":
                key = message.created_at.strftime("%Y-%m-%d")
            elif group_by == "week":
                key = message.created_at.strftime("%Y-W%U")
            else:  # month
                key = message.created_at.strftime("%Y-%m")
            
            if key not in usage_data:
                usage_data[key] = {"conversations": 0, "messages": 0}
            usage_data[key]["messages"] += 1
        
        # Ordenar dados por data
        sorted_data = sorted(usage_data.items())
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "group_by": group_by
            },
            "total_conversations": len(conversations),
            "total_messages": len(messages),
            "usage_timeline": [
                {
                    "period": key,
                    "conversations": data["conversations"],
                    "messages": data["messages"]
                }
                for key, data in sorted_data
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar relatório de uso: {str(e)}"
        )