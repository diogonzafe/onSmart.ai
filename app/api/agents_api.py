from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.db.database import get_db
from app.models.agent import Agent, AgentType
from app.models.conversation import Conversation
from app.schemas.agent import (
    AgentResponse, AgentUpdate, AgentCreate, 
    AgentBatchUpdate, AgentBatchResponse
)
from app.schemas.message import SendMessage
from app.services.agent_service import get_agent_service, AgentService
from app.core.security import get_current_active_user
from app.models.user import User
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/agents", tags=["agents"])

# ============= ENDPOINTS BÁSICOS DE AGENTES =============

@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    agent_type: Optional[AgentType] = Query(None, description="Filtrar por tipo de agente"),
    is_active: bool = Query(True, description="Filtrar apenas agentes ativos"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de agentes"),
    offset: int = Query(0, ge=0, description="Número de agentes a pular"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista todos os agentes do usuário atual."""
    try:
        agent_service = get_agent_service(db)
        
        # Listar agentes com filtros
        agents = await agent_service.list_agents(
            user_id=current_user.id,
            agent_type=agent_type,
            is_active=is_active
        )
        
        # Aplicar paginação
        total_agents = len(agents)
        paginated_agents = agents[offset:offset + limit]
        
        return paginated_agents
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtém um agente específico."""
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
        
        return agent
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.post("/", response_model=AgentResponse)
async def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cria um novo agente."""
    try:
        agent_service = get_agent_service(db)
        
        # Criar o agente
        agent = agent_service.create_agent(
            user_id=current_user.id,
            name=agent_data.name,
            description=agent_data.description,
            agent_type=agent_data.agent_type,
            template_id=agent_data.template_id,
            configuration=agent_data.configuration
        )
        
        return agent
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.patch("/{agent_id}", response_model=AgentResponse)
def patch_agent(
    agent_id: str,
    update_data: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza parcialmente um agente específico."""
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
        
        # Obter o serviço de agentes
        agent_service = get_agent_service(db)
        
        # Converter os dados de atualização para os parâmetros esperados pelo service
        update_dict = update_data.dict(exclude_unset=True)
        
        # Atualizar usando o service
        updated_agent = agent_service.update_agent(
            agent_id=agent_id,
            name=update_dict.get('name'),
            description=update_dict.get('description'),
            is_active=update_dict.get('is_active'),
            configuration=update_dict.get('configuration')
        )
        
        return updated_agent
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    agent_update: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza completamente um agente específico."""
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
        
        # Obter o serviço de agentes
        agent_service = get_agent_service(db)
        
        # Converter para dict e usar o serviço
        update_data = agent_update.dict(exclude_unset=True)
        
        updated_agent = agent_service.update_agent(
            agent_id=agent_id,
            name=update_data.get('name'),
            description=update_data.get('description'),
            is_active=update_data.get('is_active'),
            configuration=update_data.get('configuration')
        )
        
        return updated_agent
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Remove (desativa) um agente."""
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
        
        # Obter o serviço de agentes
        agent_service = get_agent_service(db)
        
        # Deletar o agente (soft delete)
        success = agent_service.delete_agent(agent_id)
        
        if success:
            return {"message": "Agente removido com sucesso"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível remover o agente"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

# ============= ENDPOINTS DE MENSAGENS =============

@router.post("/message/{conversation_id}")
async def send_message_to_agent(
    conversation_id: str,
    message_data: SendMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Envia uma mensagem para um agente em uma conversa específica."""
    try:
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
        
        # Verificar se o agente da conversa está ativo
        agent = db.query(Agent).filter(
            Agent.id == conversation.agent_id,
            Agent.is_active == True
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agente não encontrado ou inativo"
            )
        
        # Processar a mensagem
        agent_service = get_agent_service(db)
        
        response = await agent_service.process_message(
            agent_id=agent.id,
            conversation_id=conversation_id,
            message=message_data.content,
            metadata=message_data.metadata
        )
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "agent_id": agent.id,
            "user_message": response["user_message"],
            "agent_response": response["agent_response"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar mensagem: {str(e)}"
        )

# ============= ENDPOINTS ESPECÍFICOS POR TIPO =============

@router.get("/supervisor", response_model=List[AgentResponse])
async def list_supervisor_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista apenas agentes supervisores do usuário."""
    try:
        agent_service = get_agent_service(db)
        
        agents = await agent_service.list_agents(
            user_id=current_user.id,
            agent_type=AgentType.SUPERVISOR,
            is_active=True
        )
        
        return agents
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.get("/marketing", response_model=List[AgentResponse])
async def list_marketing_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista apenas agentes de marketing do usuário."""
    try:
        agent_service = get_agent_service(db)
        
        agents = await agent_service.list_agents(
            user_id=current_user.id,
            agent_type=AgentType.MARKETING,
            is_active=True
        )
        
        return agents
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.get("/sales", response_model=List[AgentResponse])
async def list_sales_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista apenas agentes de vendas do usuário."""
    try:
        agent_service = get_agent_service(db)
        
        agents = await agent_service.list_agents(
            user_id=current_user.id,
            agent_type=AgentType.SALES,
            is_active=True
        )
        
        return agents
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

@router.get("/finance", response_model=List[AgentResponse])
async def list_finance_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista apenas agentes financeiros do usuário."""
    try:
        agent_service = get_agent_service(db)
        
        agents = await agent_service.list_agents(
            user_id=current_user.id,
            agent_type=AgentType.FINANCE,
            is_active=True
        )
        
        return agents
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

# ============= ENDPOINTS EM LOTE =============

@router.post("/batch/update", response_model=AgentBatchResponse)
async def batch_update_agents(
    updates: List[AgentBatchUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza múltiplos agentes em uma única operação."""
    agent_service = get_agent_service(db)
    
    results = []
    success_count = 0
    error_count = 0
    
    for update in updates:
        try:
            # Validar entrada
            if not update.agent_id:
                results.append({
                    "id": None,
                    "status": "error",
                    "message": "agent_id é obrigatório"
                })
                error_count += 1
                continue
            
            # Verificar propriedade do agente
            try:
                agent = agent_service.get_agent(update.agent_id)
                if agent.user_id != current_user.id:
                    results.append({
                        "id": update.agent_id,
                        "status": "error",
                        "message": "Agente não pertence ao usuário atual"
                    })
                    error_count += 1
                    continue
            except ValueError:
                results.append({
                    "id": update.agent_id,
                    "status": "error", 
                    "message": "Agente não encontrado"
                })
                error_count += 1
                continue
            
            # Atualizar agente
            updated = agent_service.update_agent(
                agent_id=update.agent_id,
                name=update.name,
                description=update.description,
                is_active=update.is_active,
                configuration=update.configuration
            )
            
            results.append({
                "id": updated.id,
                "status": "success",
                "message": "Agente atualizado com sucesso",
                "data": {
                    "name": updated.name,
                    "is_active": updated.is_active
                }
            })
            success_count += 1
            
        except Exception as e:
            results.append({
                "id": update.agent_id,
                "status": "error",
                "message": f"Erro interno: {str(e)}"
            })
            error_count += 1
    
    return AgentBatchResponse(
        success_count=success_count,
        error_count=error_count,
        results=results
    )