# app/orchestration/__init__.py - Versão corrigida

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
            db_session=self.db_session
        )
        
        try:
            # Executar o grafo
            final_state = await self.execution_graph.ainvoke(initial_state)
            
            # Preparar resposta adaptada para diferentes tipos de retorno
            processing_time = time.time() - start_time
            
            # CORREÇÃO: Verificar se o final_state é válido
            if not final_state:
                logger.error("Estado final é None ou inválido")
                return self._create_error_response(
                    "Estado do sistema inválido após processamento",
                    processing_time
                )
            
            # Obter resposta final com tratamento melhorado
            final_response = self._get_final_response(final_state)
            
            # CORREÇÃO: Garantir que sempre temos uma resposta legível
            if not final_response or final_response.strip() == "":
                final_response = "Desculpe, não consegui processar sua solicitação adequadamente. Por favor, tente novamente."
            
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
                "total_actions": total_actions,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            
            # Criar resposta de fallback em caso de erro
            return self._create_error_response(str(e), time.time() - start_time)
    
    def _get_final_response(self, state: Any) -> str:
        """
        Extrai a resposta final do estado, independentemente do seu tipo.
        CORRIGIDO para evitar retornar representações de objeto como string.
        
        Args:
            state: Estado final retornado pelo grafo
            
        Returns:
            Texto da resposta final
        """
        # CORREÇÃO: Verificar se o estado é válido primeiro
        if not state:
            logger.warning("Estado fornecido é None ou inválido")
            return "Erro interno: estado do sistema inválido."
        
        # CORREÇÃO: Se o estado é uma string (representação), tentar converter
        if isinstance(state, str):
            logger.warning("Estado retornado como string - possível erro de serialização")
            return "Desculpe, houve um problema no processamento. Tente reformular sua pergunta."
        
        # Verificar método get_final_response (implementado na classe AgentState)
        if hasattr(state, "get_final_response") and callable(getattr(state, "get_final_response")):
            response = state.get_final_response()
            if response and isinstance(response, str) and response.strip():
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
            # CORREÇÃO: Verificar se responses é uma lista válida
            if not isinstance(responses, list):
                logger.warning("Responses não é uma lista válida")
                return "Processamento concluído, mas formato de resposta inválido."
            
            # Priorizar a resposta do fallback se existir
            fallback_responses = []
            for r in responses:
                agent_id = None
                if hasattr(r, "agent_id"):
                    agent_id = r.agent_id
                elif isinstance(r, dict) and "agent_id" in r:
                    agent_id = r.get("agent_id")
                
                if agent_id == "fallback_system":
                    fallback_responses.append(r)
            
            if fallback_responses:
                last_response = fallback_responses[-1]
            else:
                # Pegar a última resposta não-supervisor (se possível)
                non_supervisor_responses = []
                for r in responses:
                    agent_id = None
                    if hasattr(r, "agent_id"):
                        agent_id = r.agent_id
                    elif isinstance(r, dict) and "agent_id" in r:
                        agent_id = r.get("agent_id")
                    
                    if agent_id and not agent_id.startswith("supervisor"):
                        non_supervisor_responses.append(r)
                
                if non_supervisor_responses:
                    last_response = non_supervisor_responses[-1]
                else:
                    last_response = responses[-1]  # Se não houver não-supervisor, use a última
            
            # CORREÇÃO: Extrair conteúdo com verificação de tipos
            if hasattr(last_response, "content"):
                content = last_response.content
                if isinstance(content, str) and content.strip():
                    return content
            elif isinstance(last_response, dict) and "content" in last_response:
                content = last_response["content"]
                if isinstance(content, str) and content.strip():
                    return content
            else:
                # CORREÇÃO: Evitar retornar repr() de objeto
                logger.warning("Resposta não tem conteúdo válido")
                return "Processamento concluído, mas não foi possível extrair resposta textual."
        
        # CORREÇÃO: Verificar se há alguma informação útil no estado
        if hasattr(state, "current_message"):
            return f"Recebi sua mensagem: '{state.current_message}'. No momento, não consigo processá-la adequadamente. Por favor, tente novamente."
        
        # Retornar resposta padrão em vez de str(state)
        return "Não foi possível processar sua solicitação no momento. Por favor, tente novamente ou reformule sua pergunta."
    
    def _create_error_response(self, error_message: str, processing_time: float) -> Dict[str, Any]:
        """
        Cria uma resposta de erro padronizada.
        
        Args:
            error_message: Mensagem de erro
            processing_time: Tempo de processamento
            
        Returns:
            Resposta de erro formatada
        """
        # CORREÇÃO: Resposta amigável para erros comuns
        if "agente supervisor" in error_message.lower():
            user_friendly_message = "No momento, não há agentes supervisor configurados. Por favor, configure um agente supervisor primeiro."
        elif "não encontrado" in error_message.lower():
            user_friendly_message = "Alguns componentes necessários não foram encontrados. Verifique a configuração do sistema."
        elif "timeout" in error_message.lower():
            user_friendly_message = "O processamento está levando mais tempo que o esperado. Tente novamente em alguns instantes."
        else:
            user_friendly_message = "Ocorreu um erro interno. Nossa equipe foi notificada e está trabalhando na solução."
        
        return {
            "response": user_friendly_message,
            "processing_time": processing_time,
            "agent_responses": [],
            "agents_involved": [],
            "total_actions": 0,
            "success": False,
            "error": error_message
        }
    
    def _get_agent_responses(self, state: Any) -> List[Any]:
        """
        Extrai as respostas dos agentes do estado.
        CORRIGIDO para melhor tratamento de tipos.
        
        Args:
            state: Estado final retornado pelo grafo
            
        Returns:
            Lista de respostas de agentes
        """
        responses = []
        
        # CORREÇÃO: Verificar se o estado é válido
        if not state:
            return responses
        
        # Verificar se é um objeto com atributo responses
        if hasattr(state, "responses"):
            for resp in state.responses:
                try:
                    if hasattr(resp, "model_dump") and callable(getattr(resp, "model_dump")):
                        responses.append(resp.model_dump())
                    elif isinstance(resp, dict):
                        responses.append(resp)
                    else:
                        # CORREÇÃO: Evitar adicionar objetos inválidos
                        if hasattr(resp, "content"):
                            responses.append({"content": resp.content})
                        else:
                            responses.append({"content": "Resposta não formatada adequadamente"})
                except Exception as e:
                    logger.warning(f"Erro ao processar resposta de agente: {str(e)}")
        
        # Verificar se é um dicionário com chave 'responses'
        elif isinstance(state, dict) and "responses" in state:
            for resp in state["responses"]:
                try:
                    if hasattr(resp, "model_dump") and callable(getattr(resp, "model_dump")):
                        responses.append(resp.model_dump())
                    elif isinstance(resp, dict):
                        responses.append(resp)
                    else:
                        # CORREÇÃO: Tratamento para tipos inesperados
                        if hasattr(resp, "content"):
                            responses.append({"content": resp.content})
                        else:
                            responses.append({"content": "Resposta não formatada adequadamente"})
                except Exception as e:
                    logger.warning(f"Erro ao processar resposta de agente: {str(e)}")
        
        return responses
    
    def _get_agents_involved(self, state: Any) -> List[str]:
        """
        Extrai os agentes envolvidos no processamento.
        
        Args:
            state: Estado final retornado pelo grafo
            
        Returns:
            Lista de IDs de agentes
        """
        # CORREÇÃO: Verificar se o estado é válido
        if not state:
            return []
        
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
        # CORREÇÃO: Verificar se o estado é válido
        if not state:
            return 0
        
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