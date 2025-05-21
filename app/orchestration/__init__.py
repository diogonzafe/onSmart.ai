from typing import Dict, List, Any, Optional, Union
import logging
import time
import asyncio
from datetime import datetime

from app.orchestration.state_manager import AgentState, AgentResponse
from app.orchestration.graph_builder import GraphBuilder
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    Orquestrador principal para o sistema multi-agentes.
    Coordena o fluxo de trabalho entre agentes usando LangGraph.
    """
    
    def __init__(self, db_session=None):
        """
        Inicializa o orquestrador.
        
        Args:
            db_session: Sessão do banco de dados (opcional)
        """
        self.db_session = db_session or SessionLocal()
        self.graph_builder = GraphBuilder(self.db_session)
        self.execution_graph = self.graph_builder.create_execution_graph()
        
        logger.info("Orquestrador multi-agentes inicializado")
    
    async def process_message(
        self, 
        conversation_id: str, 
        user_id: str, 
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processa uma mensagem através do fluxo de agentes.
        
        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário
            message: Conteúdo da mensagem
            metadata: Metadados adicionais (opcional)
            
        Returns:
            Resultado do processamento
        """
        logger.info(f"Processando mensagem para conversa {conversation_id}")
        
        # Medir tempo total de processamento
        start_time = time.time()
        
        # Inicializar estado
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
            db_session=self.db_session  # Adicionar a sessão ao estado
        )
        
        try:
            # Executar o grafo
            final_state = await self.execution_graph.ainvoke(initial_state)
            
            # Preparar resposta adaptada para diferentes tipos de retorno
            processing_time = time.time() - start_time
            
            # Obter resposta final
            final_response = self._get_final_response(final_state)
            
            # Obter respostas de agentes
            agent_responses = self._get_agent_responses(final_state)
            
            # Obter agentes envolvidos
            agents_involved = self._get_agents_involved(final_state)
            
            # Obter contagem de ações
            total_actions = self._get_total_actions(final_state)
            
            # Registrar estatísticas
            logger.info(f"Mensagem processada em {processing_time:.2f}s")
            
            # Retornar resultado
            return {
                "response": final_response,
                "processing_time": processing_time,
                "agent_responses": agent_responses,
                "agents_involved": agents_involved,
                "total_actions": total_actions
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            
            # Criar resposta de fallback em caso de erro
            return {
                "response": "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde.",
                "processing_time": time.time() - start_time,
                "error": str(e)
            }
    
    def _get_final_response(self, state: Any) -> str:
        """
        Extrai a resposta final do estado, independentemente do seu tipo.
        
        Args:
            state: Estado final retornado pelo grafo
            
        Returns:
            Texto da resposta final
        """
        # Verificar método get_final_response (implementado na classe AgentState)
        if hasattr(state, "get_final_response") and callable(getattr(state, "get_final_response")):
            response = state.get_final_response()
            if response:
                return response
            
        # Obter todas as respostas e retornar a última relevante
        responses = []
        
        # Verificar se é um objeto com atributo responses
        if hasattr(state, "responses"):
            responses = state.responses
        # Verificar se é um dicionário com chave 'responses'
        elif isinstance(state, dict) and "responses" in state:
            responses = state["responses"]
        
        # Se houver respostas, retornar o conteúdo da última
        if responses:
            # Priorizar a resposta do fallback se existir
            fallback_responses = [
                r for r in responses 
                if (hasattr(r, "agent_id") and r.agent_id == "fallback_system") or
                   (isinstance(r, dict) and r.get("agent_id") == "fallback_system")
            ]
            
            if fallback_responses:
                last_response = fallback_responses[-1]
            else:
                # Pegar a última resposta não-supervisor (se possível)
                non_supervisor_responses = [
                    r for r in responses 
                    if (hasattr(r, "agent_id") and not r.agent_id.startswith("supervisor")) or
                       (isinstance(r, dict) and r.get("agent_id") and not r.get("agent_id").startswith("supervisor"))
                ]
                
                if non_supervisor_responses:
                    last_response = non_supervisor_responses[-1]
                else:
                    last_response = responses[-1]  # Se não houver não-supervisor, use a última
            
            # Extrair conteúdo
            if hasattr(last_response, "content"):
                return last_response.content
            elif isinstance(last_response, dict) and "content" in last_response:
                return last_response["content"]
            else:
                return str(last_response)
        
        # Retornar representação em string ou resposta padrão se nada funcionar
        return str(state) if state else "Não foi possível gerar uma resposta."
    
    def _get_agent_responses(self, state: Any) -> List[Any]:
        """
        Extrai as respostas dos agentes do estado.
        
        Args:
            state: Estado final retornado pelo grafo
            
        Returns:
            Lista de respostas de agentes
        """
        responses = []
        
        # Verificar se é um objeto com atributo responses
        if hasattr(state, "responses"):
            for resp in state.responses:
                if hasattr(resp, "model_dump") and callable(getattr(resp, "model_dump")):
                    responses.append(resp.model_dump())
                elif isinstance(resp, dict):
                    responses.append(resp)
                else:
                    responses.append({"content": str(resp)})
        
        # Verificar se é um dicionário com chave 'responses'
        elif isinstance(state, dict) and "responses" in state:
            for resp in state["responses"]:
                if hasattr(resp, "model_dump") and callable(getattr(resp, "model_dump")):
                    responses.append(resp.model_dump())
                elif isinstance(resp, dict):
                    responses.append(resp)
                else:
                    responses.append({"content": str(resp)})
        
        return responses
    
    def _get_agents_involved(self, state: Any) -> List[str]:
        """
        Extrai os agentes envolvidos no processamento.
        
        Args:
            state: Estado final retornado pelo grafo
            
        Returns:
            Lista de IDs de agentes
        """
        # Verificar se é um objeto com atributo processing_times
        if hasattr(state, "processing_times"):
            return list(state.processing_times.keys())
        
        # Verificar se é um dicionário com chave 'processing_times'
        if isinstance(state, dict) and "processing_times" in state:
            return list(state["processing_times"].keys())
        
        return []
    
    def _get_total_actions(self, state: Any) -> int:
        """
        Extrai o número total de ações executadas.
        
        Args:
            state: Estado final retornado pelo grafo
            
        Returns:
            Número de ações
        """
        # Verificar se é um objeto com atributo actions_history
        if hasattr(state, "actions_history"):
            return len(state.actions_history)
        
        # Verificar se é um dicionário com chave 'actions_history'
        if isinstance(state, dict) and "actions_history" in state:
            return len(state["actions_history"])
        
        return 0
    
    def __del__(self):
        """Limpeza de recursos ao destruir a instância."""
        if hasattr(self, 'db_session') and self.db_session:
            self.db_session.close()

# Singleton para acesso global
_orchestrator_instance = None

def get_orchestrator(db_session=None) -> Orchestrator:
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator(db_session)
    elif db_session is not None:
        # Atualizar a sessão do banco de dados se uma for fornecida
        _orchestrator_instance.db_session = db_session
        # Também atualizar a sessão no GraphBuilder
        _orchestrator_instance.graph_builder.db_session = db_session
    
    return _orchestrator_instance