# app/api/batch_api.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import asyncio

from app.db.database import get_db
from app.models.user import User
from app.core.security import get_current_active_user
from app.schemas.agent import AgentBatchUpdate, AgentCreate
from app.schemas.template import TemplateBatchUpdate
from app.services.agent_service import get_agent_service
from app.services.template_service import get_template_service

router = APIRouter(prefix="/api/batch", tags=["batch"])

@router.post("/agents/update")
async def batch_update_agents(
    updates: List[AgentBatchUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza múltiplos agentes em uma única operação."""
    from app.services.agent_service import get_agent_service
    agent_service = get_agent_service(db)
    
    results = []
    for update in updates:
        try:
            # Verificar propriedade do agente
            agent = agent_service.get_agent(update.agent_id)
            if agent.user_id != current_user.id:
                results.append({
                    "id": update.agent_id,
                    "status": "error",
                    "message": "Agente não pertence ao usuário atual"
                })
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
                "message": "Agente atualizado com sucesso"
            })
            
        except Exception as e:
            results.append({
                "id": update.agent_id,
                "status": "error",
                "message": str(e)
            })
    
    return {"results": results}

@router.post("/agents/create")
async def batch_create_agents(
    agents: List[AgentCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cria múltiplos agentes em uma única operação."""
    from app.services.agent_service import get_agent_service
    agent_service = get_agent_service(db)
    
    results = []
    for agent_data in agents:
        try:
            # Criar agente
            agent = agent_service.create_agent(
                user_id=current_user.id,
                name=agent_data.name,
                description=agent_data.description,
                agent_type=agent_data.agent_type,
                template_id=agent_data.template_id,
                configuration=agent_data.configuration
            )
            
            results.append({
                "id": agent.id,
                "status": "success",
                "message": "Agente criado com sucesso"
            })
            
        except Exception as e:
            results.append({
                "name": agent_data.name,
                "status": "error",
                "message": str(e)
            })
    
    return {"results": results}

@router.post("/templates/update")
async def batch_update_templates(
    updates: List[TemplateBatchUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza múltiplos templates em uma única operação."""
    from app.services.template_service import get_template_service
    template_service = get_template_service(db)
    
    results = []
    for update in updates:
        try:
            # Verificar propriedade do template
            template = template_service.get_template(update.template_id)
            if template.user_id != current_user.id:
                results.append({
                    "id": update.template_id,
                    "status": "error",
                    "message": "Template não pertence ao usuário atual"
                })
                continue
            
            # Atualizar template
            updated = template_service.update_template(
                template_id=update.template_id,
                name=update.name,
                description=update.description,
                department=update.department,
                is_public=update.is_public,
                prompt_template=update.prompt_template,
                tools_config=update.tools_config,
                llm_config=update.llm_config
            )
            
            results.append({
                "id": updated.id,
                "status": "success",
                "message": "Template atualizado com sucesso"
            })
            
        except Exception as e:
            results.append({
                "id": update.template_id,
                "status": "error",
                "message": str(e)
            })
    
    return {"results": results}