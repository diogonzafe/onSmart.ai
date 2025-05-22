# app/orchestration/enhanced_orchestrator.py
from typing import Dict, List, Any, Optional, Union
import logging
import time
import asyncio
import uuid
from datetime import datetime

from app.orchestration.state_manager import AgentState, AgentResponse
from app.orchestration.graph_builder import GraphBuilder
from app.db.database import SessionLocal
from app.models.conversation import Conversation, ConversationStatus
from app.models.user import User
from app.models.agent import Agent, AgentType

logger = logging.getLogger(__name__)

class EnhancedOrchestrator:
    """
    Orquestrador aprimorado com melhor tratamento de erros,
    validação de entrada e recuperação automática.
    """
    
    def __init__(self, db_session=None):
        """
        Inicializa o orquestrador aprimorado.
        
        Args:
            db_session: Sessão do banco de dados (opcional)
        """
        self.db_session = db_session or SessionLocal()
        self.graph_builder = GraphBuilder(self.db_session)
        self.execution_graph = self.graph_builder.create_execution_graph()
        
        # Configurações para resiliência
        self.max_retries = 3
        self.retry_delay = 1.0  # segundos
        self.default_timeout = 30.0  # segundos
        
        logger.info("Orquestrador aprimorado inicializado")
    
    async def process_message(
        self, 
        conversation_id: str, 
        user_id: str, 
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processa uma mensagem com validação e tratamento de erros aprimorados.
        
        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário
            message: Conteúdo da mensagem
            metadata: Metadados adicionais (opcional)
            
        Returns:
            Resultado do processamento
        """
        # Validar entrada
        validation_result = await self._validate_input(conversation_id, user_id, message)
        if not validation_result["valid"]:
            return {
                "error": "Entrada inválida",
                "details": validation_result["errors"],
                "success": False
            }
        
        # Obter dados validados
        conversation = validation_result["conversation"]
        user = validation_result["user"]
        agent = validation_result["agent"]
        
        logger.info(f"Processando mensagem para conversa {conversation_id} do usuário {user.name}")
        
        # Medir tempo total de processamento
        start_time = time.time()
        
        # Tentar processar com retry
        for attempt in range(self.max_retries):
            try:
                result = await self._process_with_timeout(
                    conversation_id, user_id, message, metadata, agent
                )
                
                # Sucesso - retornar resultado
                processing_time = time.time() - start_time
                result["processing_time"] = processing_time
                result["success"] = True
                result["attempt"] = attempt + 1
                
                logger.info(f"Mensagem processada com sucesso em {processing_time:.2f}s (tentativa {attempt + 1})")
                return result
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout na tentativa {attempt + 1} de {self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return await self._create_timeout_response(conversation_id, user_id, message)
            
            except Exception as e:
                logger.error(f"Erro na tentativa {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return await self._create_error_response(conversation_id, user_id, message, str(e))
        
        # Se chegou aqui, todas as tentativas falharam
        return await self._create_failure_response(conversation_id, user_id, message)
    
    async def _validate_input(self, conversation_id: str, user_id: str, message: str) -> Dict[str, Any]:
        """
        Valida a entrada do processamento.
        
        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário  
            message: Mensagem
            
        Returns:
            Resultado da validação
        """
        errors = []
        
        # Validar IDs
        if not conversation_id or conversation_id == "null":
            errors.append("conversation_id é obrigatório e não pode ser 'null'")
        
        if not user_id:
            errors.append("user_id é obrigatório")
        
        if not message or not message.strip():
            errors.append("message é obrigatória e não pode estar vazia")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        # Validar entidades no banco
        try:
            # Verificar conversa
            conversation = self.db_session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                return {
                    "valid": False, 
                    "errors": [f"Conversa {conversation_id} não encontrada"]
                }
            
            if conversation.status != ConversationStatus.ACTIVE:
                return {
                    "valid": False,
                    "errors": ["Conversa não está ativa"]
                }
            
            # Verificar usuário
            user = self.db_session.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    "valid": False,
                    "errors": [f"Usuário {user_id} não encontrado"]
                }
            
            if not user.is_active:
                return {
                    "valid": False,
                    "errors": ["Usuário não está ativo"]
                }
            
            # Verificar agente
            agent = self.db_session.query(Agent).filter(Agent.id == conversation.agent_id).first()
            if not agent:
                return {
                    "valid": False,
                    "errors": [f"Agente {conversation.agent_id} não encontrado"]
                }
            
            if not agent.is_active:
                return {
                    "valid": False,
                    "errors": ["Agente não está ativo"]
                }
            
            # Verificar permissão
            if conversation.user_id != user_id:
                return {
                    "valid": False,
                    "errors": ["Usuário não tem permissão para esta conversa"]
                }
            
            return {
                "valid": True,
                "conversation": conversation,
                "user": user,
                "agent": agent
            }
            
        except Exception as e:
            logger.error(f"Erro na validação: {str(e)}")
            return {
                "valid": False,
                "errors": [f"Erro interno na validação: {str(e)}"]
            }
    
    async def _process_with_timeout(
        self, 
        conversation_id: str, 
        user_id: str, 
        message: str,
        metadata: Optional[Dict[str, Any]],
        agent: Agent
    ) -> Dict[str, Any]:
        """
        Processa a mensagem com timeout.
        
        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário
            message: Mensagem
            metadata: Metadados
            agent: Agente da conversa
            
        Returns:
            Resultado do processamento
        """
        # Criar estado inicial
        initial_state = AgentState(
            conversation_id=conversation_id,
            user_id=user_id,
            current_message=message,
            messages=[
                {
                    "role": "user",
                    "content": message,
                    "metadata": metadata or {}
                }
            ],
            db_session=self.db_session
        )
        
        # Executar com timeout
        final_state = await asyncio.wait_for(
            self.execution_graph.ainvoke(initial_state),
            timeout=self.default_timeout
        )
        
        # Preparar resposta
        return self._prepare_response(final_state, agent)
    
    def _prepare_response(self, final_state: Any, agent: Agent) -> Dict[str, Any]:
        """
        Prepara a resposta final do processamento.
        
        Args:
            final_state: Estado final do grafo
            agent: Agente da conversa
            
        Returns:
            Resposta formatada
        """
        # Obter resposta final
        final_response = self._get_final_response(final_state)
        
        # Obter respostas de agentes
        agent_responses = self._get_agent_responses(final_state)
        
        # Obter agentes envolvidos
        agents_involved = self._get_agents_involved(final_state)
        
        # Obter contagem de ações
        total_actions = self._get_total_actions(final_state)
        
        # Informações do agente principal
        primary_agent_info = {
            "id": agent.id,
            "name": agent.name,
            "type": agent.type.value
        }
        
        return {
            "response": final_response,
            "agent_responses": agent_responses,
            "agents_involved": agents_involved,
            "total_actions": total_actions,
            "primary_agent": primary_agent_info,
            "conversation_active": True
        }
    
    async def _create_timeout_response(self, conversation_id: str, user_id: str, message: str) -> Dict[str, Any]:
        """
        Cria uma resposta para casos de timeout.
        
        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário
            message: Mensagem original
            
        Returns:
            Resposta de timeout
        """
        logger.warning(f"Timeout ao processar mensagem para conversa {conversation_id}")
        
        return {
            "response": "Desculpe, sua solicitação está levando mais tempo que o esperado para ser processada. Por favor, tente novamente em alguns instantes.",
            "success": False,
            "error_type": "timeout",
            "retry_suggested": True,
            "processing_time": self.default_timeout
        }
    
    async def _create_error_response(self, conversation_id: str, user_id: str, message: str, error: str) -> Dict[str, Any]:
        """
        Cria uma resposta para casos de erro.
        
        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário
            message: Mensagem original
            error: Descrição do erro
            
        Returns:
            Resposta de erro
        """
        logger.error(f"Erro ao processar mensagem para conversa {conversation_id}: {error}")
        
        # Criar resposta amigável baseada no tipo de erro
        if "rate limit" in error.lower():
            friendly_message = "Sistema temporariamente sobrecarregado. Tente novamente em alguns minutos."
        elif "connection" in error.lower():
            friendly_message = "Problemas de conectividade. Verificando sistemas..."
        elif "authentication" in error.lower():
            friendly_message = "Problema de autenticação. Por favor, faça login novamente."
        else:
            friendly_message = "Ocorreu um erro inesperado. Nossa equipe foi notificada e está trabalhando na solução."
        
        return {
            "response": friendly_message,
            "success": False,
            "error_type": "processing_error",
            "retry_suggested": True,
            "technical_error": error if logger.level <= logging.DEBUG else None
        }
    
    async def _create_failure_response(self, conversation_id: str, user_id: str, message: str) -> Dict[str, Any]:
        """
        Cria uma resposta para quando todas as tentativas falharam.
        
        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário
            message: Mensagem original
            
        Returns:
            Resposta de falha
        """
        logger.error(f"Todas as tentativas falharam para conversa {conversation_id}")
        
        return {
            "response": "Não foi possível processar sua solicitação no momento. Por favor, tente novamente mais tarde ou entre em contato com o suporte se o problema persistir.",
            "success": False,
            "error_type": "max_retries_exceeded",
            "retry_suggested": False,
            "max_retries": self.max_retries
        }
    
    # Métodos auxiliares (mantidos do orquestrador original)
    def _get_final_response(self, state: Any) -> str:
        """Extrai a resposta final do estado."""
        if hasattr(state, "get_final_response") and callable(getattr(state, "get_final_response")):
            response = state.get_final_response()
            if response:
                return response
        
        # Fallback para extração manual
        responses = []
        if hasattr(state, "responses"):
            responses = state.responses
        elif isinstance(state, dict) and "responses" in state:
            responses = state["responses"]
        
        if responses:
            last_response = responses[-1]
            if hasattr(last_response, "content"):
                return last_response.content
            elif isinstance(last_response, dict) and "content" in last_response:
                return last_response["content"]
        
        return "Processamento concluído, mas não foi possível gerar uma resposta textual."
    
    def _get_agent_responses(self, state: Any) -> List[Any]:
        """Extrai as respostas dos agentes do estado."""
        responses = []
        
        if hasattr(state, "responses"):
            for resp in state.responses:
                if hasattr(resp, "model_dump") and callable(getattr(resp, "model_dump")):
                    responses.append(resp.model_dump())
                elif isinstance(resp, dict):
                    responses.append(resp)
                else:
                    responses.append({"content": str(resp)})
        
        return responses
    
    def _get_agents_involved(self, state: Any) -> List[str]:
        """Extrai os agentes envolvidos no processamento."""
        if hasattr(state, "processing_times"):
            return list(state.processing_times.keys())
        elif isinstance(state, dict) and "processing_times" in state:
            return list(state["processing_times"].keys())
        return []
    
    def _get_total_actions(self, state: Any) -> int:
        """Extrai o número total de ações executadas."""
        if hasattr(state, "actions_history"):
            return len(state.actions_history)
        elif isinstance(state, dict) and "actions_history" in state:
            return len(state["actions_history"])
        return 0
    
    def __del__(self):
        """Limpeza de recursos ao destruir a instância."""
        if hasattr(self, 'db_session') and self.db_session:
            self.db_session.close()


# Função factory para substituir o orquestrador original
def get_enhanced_orchestrator(db_session=None) -> EnhancedOrchestrator:
    """
    Obtém uma instância do orquestrador aprimorado.
    
    Args:
        db_session: Sessão do banco de dados (opcional)
        
    Returns:
        Instância do EnhancedOrchestrator
    """
    return EnhancedOrchestrator(db_session)