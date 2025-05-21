# app/core/tenant.py
from sqlalchemy.orm import Session
from fastapi import Request
import logging

logger = logging.getLogger(__name__)

def tenant_filter(query, model, request=None, tenant_id=None):
    """
    Aplica filtro de tenant a uma query SQLAlchemy.
    
    Args:
        query: SQLAlchemy query
        model: Modelo SQLAlchemy
        request: FastAPI Request (opcional)
        tenant_id: ID do tenant específico (opcional)
        
    Returns:
        Query filtrada por tenant
    """
    # Determinar o tenant_id (prioridade para o parâmetro explícito)
    effective_tenant_id = tenant_id
    
    if not effective_tenant_id and request and hasattr(request.state, "tenant_id"):
        effective_tenant_id = request.state.tenant_id
    
    # Se temos um tenant_id e o modelo tem o campo organization_id, aplicar filtro
    if effective_tenant_id and hasattr(model, "organization_id"):
        logger.debug(f"Aplicando filtro de tenant {effective_tenant_id} para modelo {model.__name__}")
        return query.filter(model.organization_id == effective_tenant_id)
    
    return query