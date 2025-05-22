from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.agent import Agent
from app.schemas.agent import AgentResponse, AgentUpdate
from app.services.agent_service import get_agent_service, AgentService
from app.core.security import get_current_active_user
from app.models.user import User
from datetime import datetime

router = APIRouter()

@router.patch("/agents/{agent_id}", response_model=AgentResponse)
def patch_agent(
    agent_id: str,
    update_data: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Atualiza parcialmente um agente específico.
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
        # Erros do service (como agente não encontrado)
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

@router.put("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    agent_update: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Atualiza completamente um agente específico.
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