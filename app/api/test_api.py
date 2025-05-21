# app/api/test_api.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
import uuid

from app.db.database import get_db
from app.models.user import User
from app.core.security import get_current_active_user
from app.services.agent_service import get_agent_service
from app.services.template_service import get_template_service

router = APIRouter(prefix="/api/test", tags=["test"])

@router.post("/agent")
async def test_agent(
    agent_data: Dict[str, Any] = Body(...),
    message: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Testa um agente sem criar conversa permanente.
    Útil para testar configurações antes de salvar.
    """
    # Obter o serviço de agentes
    from app.services.agent_service import get_agent_service
    agent_service = get_agent_service(db)
    
    try:
        # Criar agente temporário
        agent_type = agent_data.get("agent_type")
        template_id = agent_data.get("template_id")
        configuration = agent_data.get("configuration", {})
        
        temp_agent = agent_service.create_agent(
            user_id=current_user.id,
            name=f"Temp Agent {uuid.uuid4()}",
            description="Agente temporário para teste",
            agent_type=agent_type,
            template_id=template_id,
            configuration=configuration
        )
        
        # Criar conversa temporária
        from app.models.conversation import Conversation, ConversationStatus
        temp_conversation = Conversation(
            id=str(uuid.uuid4()),
            title="Teste Temporário",
            user_id=current_user.id,
            agent_id=temp_agent.id,
            status=ConversationStatus.ACTIVE,
            metadata={"temp": True, "test": True}
        )
        
        db.add(temp_conversation)
        db.commit()
        
        # Processar mensagem
        response = await agent_service.process_message(
            agent_id=temp_agent.id,
            conversation_id=temp_conversation.id,
            message=message
        )
        
        # Limpar recursos temporários
        db.delete(temp_conversation)
        agent_service.delete_agent(temp_agent.id)
        db.commit()
        
        return {
            "agent_type": agent_type,
            "template_id": template_id,
            "message": message,
            "response": response.get("agent_response", {}),
            "temp": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao testar agente: {str(e)}")

@router.post("/template/render")
async def test_template_render(
    template_data: Dict[str, Any] = Body(...),
    variables: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Renderiza um template com as variáveis fornecidas.
    Útil para preview antes de salvar.
    """
    # Obter o serviço de templates
    from app.services.template_service import get_template_service
    template_service = get_template_service(db)
    
    try:
        # Extrair dados necessários
        prompt_template = template_data.get("prompt_template", "")
        
        # Preview do template
        preview = template_service.preview_template(
            template_data=template_data,
            variables=variables
        )
        
        return {
            "preview": preview,
            "variables_used": list(variables.keys())
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao renderizar template: {str(e)}")