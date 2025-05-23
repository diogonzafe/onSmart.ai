# app/core/exceptions.py
from typing import Optional, Dict, Any
from enum import Enum

class ErrorCode(str, Enum):
    """Códigos padronizados de erro."""
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    TEMPLATE_INVALID = "TEMPLATE_INVALID"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    LLM_ERROR = "LLM_ERROR"

class BaseException(Exception):
    """Exceção base do sistema."""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode, 
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.user_message = user_message or self._get_user_friendly_message()
        super().__init__(self.message)
    
    def _get_user_friendly_message(self) -> str:
        """Retorna mensagem amigável para o usuário."""
        friendly_messages = {
            ErrorCode.AGENT_NOT_FOUND: "O agente solicitado não foi encontrado.",
            ErrorCode.TEMPLATE_INVALID: "Há um problema com a configuração do template.",
            ErrorCode.PROCESSING_ERROR: "Ocorreu um erro no processamento. Tente novamente.",
            ErrorCode.RATE_LIMIT_EXCEEDED: "Muitas solicitações. Aguarde alguns momentos.",
            ErrorCode.CONVERSATION_NOT_FOUND: "Conversa não encontrada.",
            ErrorCode.VALIDATION_ERROR: "Os dados fornecidos são inválidos.",
            ErrorCode.LLM_ERROR: "Erro no serviço de IA. Tente novamente em instantes."
        }
        return friendly_messages.get(self.error_code, "Ocorreu um erro inesperado.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte exceção para dicionário."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details
        }

class AgentException(BaseException):
    """Exceções relacionadas a agentes."""
    pass

class TemplateException(BaseException):
    """Exceções relacionadas a templates."""
    pass

class ProcessingException(BaseException):
    """Exceções de processamento."""
    pass

# app/core/error_handler.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.core.exceptions import BaseException, ErrorCode
import logging

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    """Handler global para exceções."""
    
    if isinstance(exc, BaseException):
        # Exceção conhecida do sistema
        logger.error(f"Known exception: {exc.error_code} - {exc.message}", extra={
            "error_code": exc.error_code,
            "details": exc.details,
            "path": request.url.path
        })
        
        status_code = {
            ErrorCode.AGENT_NOT_FOUND: 404,
            ErrorCode.TEMPLATE_INVALID: 400,
            ErrorCode.PROCESSING_ERROR: 500,
            ErrorCode.RATE_LIMIT_EXCEEDED: 429,
            ErrorCode.CONVERSATION_NOT_FOUND: 404,
            ErrorCode.VALIDATION_ERROR: 400,
            ErrorCode.LLM_ERROR: 503
        }.get(exc.error_code, 500)
        
        return JSONResponse(
            status_code=status_code,
            content=exc.to_dict()
        )
    
    elif isinstance(exc, HTTPException):
        # Exceção HTTP do FastAPI
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": "HTTP_ERROR",
                "message": str(exc.detail),
                "user_message": "Erro na requisição."
            }
        )
    
    else:
        # Exceção não tratada
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "user_message": "Erro interno do servidor. Nossa equipe foi notificada."
            }
        )

# Exemplo de uso melhorado em um serviço
# app/services/agent_service.py (modificado)
from app.core.exceptions import AgentException, ErrorCode

# Certifique-se de importar o modelo Agent do local correto
from app.models.agent import Agent  # Ajuste o caminho conforme sua estrutura de projeto

class AgentService:
    def get_agent(self, agent_id: str) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise AgentException(
                message=f"Agent with ID {agent_id} not found in database",
                error_code=ErrorCode.AGENT_NOT_FOUND,
                details={"agent_id": agent_id},
                user_message="O agente solicitado não foi encontrado. Verifique se o ID está correto."
            )
        return agent