from typing import Dict, List, Any, Optional
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
            ]
        )
        
        try:
            # Executar o grafo
            final_state = await self.execution_graph.ainvoke(initial_state)
            
            # Preparar resposta
            final_response = final_state.get_final_response()
            processing_time = time.time() - start_time
            
            # Registrar estatísticas
            logger.info(f"Mensagem processada em {processing_time:.2f}s com {len(final_state.responses)} respostas de agentes")
            
            # Retornar resultado
            return {
                "response": final_response,
                "processing_time": processing_time,
                "agent_responses": [resp.model_dump() for resp in final_state.responses],
                "agents_involved": list(final_state.processing_times.keys()),
                "total_actions": len(final_state.actions_history)
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            
            # Criar resposta de fallback em caso de erro
            return {
                "response": "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde.",
                "processing_time": time.time() - start_time,
                "error": str(e)
            }
    
    def __del__(self):
        """Limpeza de recursos ao destruir a instância."""
        if hasattr(self, 'db_session') and self.db_session:
            self.db_session.close()

# Singleton para acesso global
_orchestrator_instance = None

def get_orchestrator(db_session=None) -> Orchestrator:
    """
    Obtém a instância do orquestrador.
    
    Args:
        db_session: Sessão do banco de dados (opcional)
        
    Returns:
        Instância do Orchestrator
    """
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator(db_session)
    
    return _orchestrator_instance