# app/api/agents_api.py - Reorganizado: Foco na gestão de agentes

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.db.database import get_db
from app.models.agent import Agent, AgentType
from app.models.template import Template
from app.schemas.agent import (
    AgentCreate, AgentUpdate, AgentResponse, 
    AgentWithTools, AgentConfiguration
)
from app.services.agent_service import get_agent_service
from app.core.security import get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/api/agents", tags=["agents"])

# =============================================================================
# 🤖 CRIAÇÃO E GESTÃO DE AGENTES
# =============================================================================

@router.post("/", response_model=AgentResponse)
async def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🤖 Cria um novo agente baseado em template
    
    Fluxo:
    1. Valida o template selecionado
    2. Cria o agente com configurações específicas
    3. Retorna o agente criado
    """
    try:
        agent_service = get_agent_service(db)
        
        # Validar tipo de agente
        if not AgentType.is_valid(agent_data.agent_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de agente inválido. Valores válidos: {', '.join(AgentType.get_all_values())}"
            )
        
        # Converter string para enum se necessário
        if isinstance(agent_data.agent_type, str):
            agent_type_enum = AgentType(agent_data.agent_type)
        else:
            agent_type_enum = agent_data.agent_type
        
        # Criar agente
        agent = agent_service.create_agent(
            user_id=current_user.id,
            name=agent_data.name,
            description=agent_data.description,
            agent_type=agent_type_enum,
            template_id=agent_data.template_id,
            configuration=agent_data.configuration
        )
        
        return AgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            user_id=agent.user_id,
            agent_type=agent.type,
            template_id=agent.template_id,
            configuration=agent.configuration,
            is_active=agent.is_active,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar agente: {str(e)}"
        )

@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    agent_type: Optional[AgentType] = Query(None),
    is_active: bool = Query(True),
    include_templates: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📋 Lista agentes do usuário com filtros
    """
    try:
        agent_service = get_agent_service(db)
        
        agents = await agent_service.list_agents(
            user_id=current_user.id,
            agent_type=agent_type,
            is_active=is_active
        )
        
        result = []
        for agent in agents:
            agent_data = AgentResponse(
                id=agent.id,
                name=agent.name,
                description=agent.description,
                user_id=agent.user_id,
                agent_type=agent.type,
                template_id=agent.template_id,
                configuration=agent.configuration,
                is_active=agent.is_active,
                created_at=agent.created_at,
                updated_at=agent.updated_at
            )
            
            # Incluir informações do template se solicitado
            if include_templates and agent.template:
                agent_data.template_info = {
                    "name": agent.template.name,
                    "department": agent.template.department.value
                }
            
            result.append(agent_data)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar agentes: {str(e)}"
        )

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    include_statistics: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🔍 Obtém detalhes de um agente específico
    """
    try:
        agent_service = get_agent_service(db)
        agent = agent_service.get_agent(agent_id)
        
        # Verificar propriedade
        if agent.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a este agente"
            )
        
        response_data = AgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            user_id=agent.user_id,
            agent_type=agent.type,
            template_id=agent.template_id,
            configuration=agent.configuration,
            is_active=agent.is_active,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        )
        
        # Incluir estatísticas se solicitado
        if include_statistics:
            from app.models.conversation import Conversation
            from app.models.message import Message
            
            # Contar conversas
            conversation_count = db.query(Conversation).filter(
                Conversation.agent_id == agent_id
            ).count()
            
            # Contar mensagens processadas
            message_count = db.query(Message).join(Conversation).filter(
                Conversation.agent_id == agent_id,
                Message.role != MessageRole.HUMAN
            ).count()
            
            response_data.statistics = {
                "conversations": conversation_count,
                "messages_processed": message_count,
                "last_activity": agent.updated_at.isoformat()
            }
        
        return response_data
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter agente: {str(e)}"
        )

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ✏️ Atualiza um agente existente
    """
    try:
        agent_service = get_agent_service(db)
        
        # Verificar se o agente existe e pertence ao usuário
        existing_agent = agent_service.get_agent(agent_id)
        if existing_agent.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a este agente"
            )
        
        # Atualizar agente
        updated_agent = agent_service.update_agent(
            agent_id=agent_id,
            name=agent_data.name,
            description=agent_data.description,
            is_active=agent_data.is_active,
            configuration=agent_data.configuration
        )
        
        return AgentResponse(
            id=updated_agent.id,
            name=updated_agent.name,
            description=updated_agent.description,
            user_id=updated_agent.user_id,
            agent_type=updated_agent.type,
            template_id=updated_agent.template_id,
            configuration=updated_agent.configuration,
            is_active=updated_agent.is_active,
            created_at=updated_agent.created_at,
            updated_at=updated_agent.updated_at
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar agente: {str(e)}"
        )

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    force: bool = Query(False, description="Forçar remoção mesmo com conversas ativas"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    🗑️ Remove um agente (soft delete)
    """
    try:
        agent_service = get_agent_service(db)
        
        # Verificar propriedade
        agent = agent_service.get_agent(agent_id)
        if agent.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a este agente"
            )
        
        # Verificar se há conversas ativas
        if not force:
            from app.models.conversation import Conversation, ConversationStatus
            active_conversations = db.query(Conversation).filter(
                Conversation.agent_id == agent_id,
                Conversation.status == ConversationStatus.ACTIVE
            ).count()
            
            if active_conversations > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agente possui {active_conversations} conversas ativas. Use force=true para forçar remoção."
                )
        
        # Remover agente
        success = agent_service.delete_agent(agent_id)
        
        if success:
            return {
                "success": True,
                "message": "Agente desativado com sucesso",
                "agent_id": agent_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao desativar agente"
            )
            
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao remover agente: {str(e)}"
        )

# =============================================================================
# ⚙️ CONFIGURAÇÃO E VALIDAÇÃO
# =============================================================================

@router.post("/{agent_id}/validate-config")
async def validate_agent_configuration(
    agent_id: str,
    configuration: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ✅ Valida configuração de um agente
    """
    try:
        agent_service = get_agent_service(db)
        
        # Verificar propriedade
        agent = agent_service.get_agent(agent_id)
        if agent.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a este agente"
            )
        
        # Obter template para validação
        template = db.query(Template).filter(Template.id == agent.template_id).first()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template do agente não encontrado"
            )
        
        # Validar configuração usando o template manager
        from app.templates.base import get_template_manager
        template_manager = get_template_manager()
        
        # Carregar template se necessário
        processed_template = template_manager.load_template(template)
        
        # Validar variáveis
        template_manager._validate_variables(
            processed_template["variables"], 
            configuration
        )
        
        return {
            "valid": True,
            "message": "Configuração válida",
            "template_variables": processed_template["variables"]
        }
        
    except ValueError as e:
        return {
            "valid": False,
            "message": str(e),
            "errors": [str(e)]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao validar configuração: {str(e)}"
        )

@router.get("/{agent_id}/config-template")
async def get_agent_config_template(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📋 Obtém template de configuração para um agente
    """
    try:
        agent_service = get_agent_service(db)
        
        # Verificar propriedade
        agent = agent_service.get_agent(agent_id)
        if agent.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a este agente"
            )
        
        # Obter configurações específicas do departamento
        dept_config = agent.get_department_config()
        
        return {
            "agent_type": agent.type.value,
            "required_fields": dept_config["required_fields"],
            "optional_fields": dept_config["optional_fields"],
            "current_configuration": agent.configuration,
            "template_id": agent.template_id
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter template de configuração: {str(e)}"
        )

# =============================================================================
# 📊 ESTATÍSTICAS E STATUS
# =============================================================================

@router.get("/{agent_id}/statistics")
async def get_agent_statistics(
    agent_id: str,
    period: str = Query("week", regex="^(day|week|month|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    📊 Obtém estatísticas detalhadas de um agente
    """
    # Delegar para o metrics_api para evitar duplicação
    from app.api.metrics_api import get_agent_metrics
    
    return await get_agent_metrics(
        agent_id=agent_id,
        period=period,
        db=db,
        current_user=current_user
    )

@router.get("/{agent_id}/status")
async def get_agent_status(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    ⚡ Obtém status atual de um agente
    """
    try:
        agent_service = get_agent_service(db)
        
        # Verificar propriedade
        agent = agent_service.get_agent(agent_id)
        if agent.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a este agente"
            )
        
        # Verificar conversas ativas
        from app.models.conversation import Conversation, ConversationStatus
        active_conversations = db.query(Conversation).filter(
            Conversation.agent_id == agent_id,
            Conversation.status == ConversationStatus.ACTIVE
        ).count()
        
        return {
            "agent_id": agent_id,
            "name": agent.name,
            "is_active": agent.is_active,
            "type": agent.type.value,
            "active_conversations": active_conversations,
            "last_updated": agent.updated_at.isoformat(),
            "status": "active" if agent.is_active else "inactive",
            "configuration_complete": bool(agent.configuration)
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter status do agente: {str(e)}"
        )