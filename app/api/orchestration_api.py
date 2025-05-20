from fastapi import APIRouter, Depends, HTTPException, Body, Path
from typing import Dict, List, Any, Optional
import logging
import time

from app.models.user import User
from app.core.security import get_current_active_user
from app.orchestration import get_orchestrator
from app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])

@router.post("/process")
async def process_message(
    conversation_id: str = Body(..., embed=True),
    message: str = Body(..., embed=True),
    metadata: Optional[Dict[str, Any]] = Body(None, embed=True),
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db)
):
    """
    Processa uma mensagem através do orquestrador de agentes.
    
    Args:
        conversation_id: ID da conversa
        message: Texto da mensagem
        metadata: Metadados adicionais (opcional)
        
    Returns:
        Resultado do processamento
    """
    start_time = time.time()
    
    try:
        # Obter orquestrador
        orchestrator = get_orchestrator(db)
        
        # Processar mensagem
        result = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message=message,
            metadata=metadata
        )
        
        # Adicionar informações de tempo
        processing_time = time.time() - start_time
        result["api_processing_time"] = processing_time
        
        return result
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem via orquestrador: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro no processamento: {str(e)}")

@router.get("/agents/{conversation_id}")
async def get_conversation_agents(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db)
):
    """
    Obtém informações sobre os agentes envolvidos em uma conversa.
    
    Args:
        conversation_id: ID da conversa
        
    Returns:
        Lista de agentes e suas contribuições
    """
    # Aqui você implementaria a lógica para obter informações dos agentes
    # que participaram da conversa específica
    
    return {
        "conversation_id": conversation_id,
        "agents": []  # Lista a ser preenchida com dados reais
    }