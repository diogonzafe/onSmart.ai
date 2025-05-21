# app/api/metrics_api.py
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

from app.db.database import get_db
from app.models.user import User
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.metrics import AgentMetrics, UserFeedback
from app.core.security import get_current_active_user
from app.schemas.metrics import AgentMetricsCreate, UserFeedbackCreate, AgentPerformanceSummary

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("/agents/{agent_id}")
async def get_agent_metrics(
    agent_id: str,
    period: str = Query("week", regex="^(day|week|month|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtém métricas de um agente específico."""
    # Verificar acesso ao agente
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
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
    total_count = len(metrics)
    avg_response_time = sum(m.response_time for m in metrics) / total_count if total_count > 0 else 0
    
    # Contar mensagens e conversas
    conversations = db.query(Conversation).filter(
        Conversation.agent_id == agent_id,
        Conversation.user_id == current_user.id,
        Conversation.created_at >= start_date
    ).all()
    
    conversation_count = len(conversations)
    conversation_ids = [c.id for c in conversations]
    
    messages = db.query(Message).filter(
        Message.conversation_id.in_(conversation_ids)
    ).all()
    
    message_count = len(messages)
    
    # Análise de ferramentas usadas
    tools_usage = {}
    for metric in metrics:
        if metric.tools_used:
            for tool, count in metric.tools_used.items():
                tools_usage[tool] = tools_usage.get(tool, 0) + count
    
    # Feedback médio
    feedbacks = db.query(UserFeedback).filter(
        UserFeedback.message_id.in_([m.id for m in messages]),
        UserFeedback.created_at >= start_date
    ).all()
    
    avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks) if feedbacks else None
    
    # Resumo de performance
    performance_summary = AgentPerformanceSummary(
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
    
    return performance_summary

@router.get("/conversations/{conversation_id}")
async def get_conversation_metrics(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtém métricas de uma conversa específica."""
    # Verificar acesso à conversa
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Buscar métricas associadas
    metrics = db.query(AgentMetrics).filter(
        AgentMetrics.conversation_id == conversation_id
    ).all()
    
    # Buscar mensagens e feedback
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).all()
    
    message_count = len(messages)
    message_ids = [m.id for m in messages]
    
    # Feedback para mensagens
    feedbacks = db.query(UserFeedback).filter(
        UserFeedback.message_id.in_(message_ids)
    ).all()
    
    feedback_count = len(feedbacks)
    avg_rating = sum(f.rating for f in feedbacks) / feedback_count if feedback_count > 0 else None
    
    # Calcular métricas agregadas
    avg_response_time = sum(m.response_time for m in metrics) / len(metrics) if metrics else 0
    total_tokens = sum(m.llm_tokens or 0 for m in metrics)
    
    # Análise de ferramentas usadas
    tools_usage = {}
    for metric in metrics:
        if metric.tools_used:
            for tool, count in metric.tools_used.items():
                tools_usage[tool] = tools_usage.get(tool, 0) + count
    
    return {
        "conversation_id": conversation_id,
        "agent_id": conversation.agent_id,
        "created_at": conversation.created_at,
        "message_count": message_count,
        "avg_response_time": avg_response_time,
        "total_tokens": total_tokens,
        "tools_usage": tools_usage,
        "feedback": {
            "count": feedback_count,
            "avg_rating": avg_rating
        }
    }

@router.post("/feedback")
async def create_feedback(
    feedback_data: UserFeedbackCreate,
    message_id: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Envia feedback para uma mensagem."""
    # Verificar acesso à mensagem
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    
    conversation = db.query(Conversation).filter(
        Conversation.id == message.conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=403, detail="Acesso negado a esta mensagem")
    
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
        return {"message": "Feedback atualizado com sucesso", "id": existing_feedback.id}
    
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
    
    return {"message": "Feedback enviado com sucesso", "id": feedback.id}