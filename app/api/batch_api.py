# app/api/batch_api.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import asyncio
import logging
from pydantic import ValidationError

from app.db.database import get_db
from app.models.user import User
from app.core.security import get_current_active_user
from app.schemas.agent import AgentBatchUpdate, AgentCreate, AgentBatchResponse
from app.schemas.template import TemplateBatchUpdate
from app.services.agent_service import get_agent_service
from app.services.template_service import get_template_service
from app.models.agent import AgentType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch", tags=["batch"])

@router.post("/agents/update", response_model=AgentBatchResponse)
async def batch_update_agents(
    updates: List[AgentBatchUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Atualiza múltiplos agentes em uma única operação.
    
    Args:
        updates: Lista de atualizações de agentes
        db: Sessão do banco de dados
        current_user: Usuário autenticado
        
    Returns:
        Resultado das operações de atualização
    """
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
            
        except ValidationError as e:
            results.append({
                "id": update.agent_id,
                "status": "error",
                "message": f"Erro de validação: {str(e)}"
            })
            error_count += 1
            
        except Exception as e:
            logger.error(f"Erro ao atualizar agente {update.agent_id}: {str(e)}")
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

@router.post("/agents/create", response_model=AgentBatchResponse)
async def batch_create_agents(
    agents: List[AgentCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cria múltiplos agentes em uma única operação.
    
    Args:
        agents: Lista de dados para criação de agentes
        db: Sessão do banco de dados
        current_user: Usuário autenticado
        
    Returns:
        Resultado das operações de criação
    """
    agent_service = get_agent_service(db)
    
    results = []
    success_count = 0
    error_count = 0
    
    for agent_data in agents:
        try:
            # Validação básica
            if not agent_data.name or not agent_data.name.strip():
                results.append({
                    "name": agent_data.name or "Sem nome",
                    "status": "error",
                    "message": "Nome do agente é obrigatório"
                })
                error_count += 1
                continue
            
            # Validar tipo de agente
            if not AgentType.is_valid(agent_data.agent_type):
                results.append({
                    "name": agent_data.name,
                    "status": "error",
                    "message": f"Tipo de agente inválido. Valores válidos: {', '.join(AgentType.get_all_values())}"
                })
                error_count += 1
                continue
            
            # Converter agent_type para o enum se necessário
            if isinstance(agent_data.agent_type, str):
                agent_type_enum = AgentType(agent_data.agent_type)
            else:
                agent_type_enum = agent_data.agent_type
            
            # Criar agente
            agent = agent_service.create_agent(
                user_id=current_user.id,
                name=agent_data.name.strip(),
                description=agent_data.description,
                agent_type=agent_type_enum,
                template_id=agent_data.template_id,
                configuration=agent_data.configuration or {}
            )
            
            results.append({
                "id": agent.id,
                "name": agent.name,
                "status": "success",
                "message": "Agente criado com sucesso",
                "data": {
                    "agent_type": agent.type.value,
                    "template_id": agent.template_id
                }
            })
            success_count += 1
            
        except ValidationError as e:
            results.append({
                "name": agent_data.name if hasattr(agent_data, 'name') else "Desconhecido",
                "status": "error",
                "message": f"Erro de validação: {str(e)}"
            })
            error_count += 1
            
        except ValueError as e:
            results.append({
                "name": agent_data.name,
                "status": "error",
                "message": str(e)
            })
            error_count += 1
            
        except Exception as e:
            logger.error(f"Erro ao criar agente {agent_data.name}: {str(e)}")
            results.append({
                "name": agent_data.name,
                "status": "error",
                "message": f"Erro interno: {str(e)}"
            })
            error_count += 1
    
    return AgentBatchResponse(
        success_count=success_count,
        error_count=error_count,
        results=results
    )

@router.post("/templates/update")
async def batch_update_templates(
    updates: List[TemplateBatchUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza múltiplos templates em uma única operação."""
    template_service = get_template_service(db)
    
    results = []
    success_count = 0
    error_count = 0
    
    for update in updates:
        try:
            # Verificar propriedade do template
            try:
                template = template_service.get_template(update.template_id)
                if template.user_id != current_user.id:
                    results.append({
                        "id": update.template_id,
                        "status": "error",
                        "message": "Template não pertence ao usuário atual"
                    })
                    error_count += 1
                    continue
            except ValueError:
                results.append({
                    "id": update.template_id,
                    "status": "error",
                    "message": "Template não encontrado"
                })
                error_count += 1
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
                "message": "Template atualizado com sucesso",
                "data": {
                    "name": updated.name,
                    "department": updated.department.value
                }
            })
            success_count += 1
            
        except ValidationError as e:
            results.append({
                "id": update.template_id,
                "status": "error",
                "message": f"Erro de validação: {str(e)}"
            })
            error_count += 1
            
        except Exception as e:
            logger.error(f"Erro ao atualizar template {update.template_id}: {str(e)}")
            results.append({
                "id": update.template_id,
                "status": "error",
                "message": f"Erro interno: {str(e)}"
            })
            error_count += 1
    
    return {
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }

@router.get("/agents/types")
async def get_agent_types():
    """
    Retorna todos os tipos de agentes disponíveis.
    
    Returns:
        Lista de tipos de agentes válidos
    """
    return {
        "agent_types": [
            {
                "value": agent_type.value,
                "display_name": agent_type.value.title(),
                "description": _get_agent_type_description(agent_type)
            }
            for agent_type in AgentType
        ]
    }

def _get_agent_type_description(agent_type: AgentType) -> str:
    """Retorna a descrição de um tipo de agente."""
    descriptions = {
        AgentType.SUPERVISOR: "Agente que coordena outros agentes e gerencia fluxos de trabalho",
        AgentType.MARKETING: "Agente especializado em marketing, publicidade e comunicação",
        AgentType.SALES: "Agente especializado em vendas, negociação e gestão de clientes",
        AgentType.FINANCE: "Agente especializado em finanças, contabilidade e análises financeiras",
        AgentType.CUSTOM: "Agente personalizado com configuração específica"
    }
    return descriptions.get(agent_type, "Agente personalizado")

@router.post("/agents/validate")
async def validate_agent_data(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Valida dados de um agente sem criá-lo.
    
    Args:
        agent_data: Dados do agente para validação
        current_user: Usuário autenticado
        
    Returns:
        Resultado da validação
    """
    try:
        # Validação básica já é feita pelo Pydantic
        
        # Validações adicionais
        errors = []
        warnings = []
        
        # Verificar se o nome não está vazio
        if not agent_data.name or not agent_data.name.strip():
            errors.append("Nome do agente é obrigatório")
        
        # Verificar tipo de agente
        if not AgentType.is_valid(agent_data.agent_type):
            errors.append(f"Tipo de agente inválido. Valores válidos: {', '.join(AgentType.get_all_values())}")
        
        # Validar configuração baseada no tipo
        if agent_data.configuration:
            agent_type_enum = AgentType(agent_data.agent_type)
            dept_config = _get_department_config(agent_type_enum)
            
            # Verificar campos obrigatórios
            for required_field in dept_config.get("required_fields", []):
                if required_field not in agent_data.configuration:
                    warnings.append(f"Campo recomendado ausente: {required_field}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "agent_type": agent_data.agent_type,
            "template_id": agent_data.template_id
        }
        
    except ValidationError as e:
        return {
            "valid": False,
            "errors": [str(e)],
            "warnings": []
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Erro de validação: {str(e)}"],
            "warnings": []
        }

def _get_department_config(agent_type: AgentType) -> Dict[str, List[str]]:
    """Retorna configurações específicas do departamento."""
    configs = {
        AgentType.MARKETING: {
            "required_fields": ["company_name", "primary_platform", "brand_tone"],
            "optional_fields": ["target_audience", "differentials", "metric_priority"]
        },
        AgentType.SALES: {
            "required_fields": ["company_name", "product_category", "sales_style"],
            "optional_fields": ["pricing_policy", "payment_terms", "discount_level"]
        },
        AgentType.FINANCE: {
            "required_fields": ["company_name", "analysis_type", "currency"],
            "optional_fields": ["competitors", "key_indicators", "analysis_period"]
        },
        AgentType.SUPERVISOR: {
            "required_fields": ["company_name"],
            "optional_fields": ["industry", "priority"]
        },
        AgentType.CUSTOM: {
            "required_fields": [],
            "optional_fields": []
        }
    }
    return configs.get(agent_type, configs[AgentType.CUSTOM])