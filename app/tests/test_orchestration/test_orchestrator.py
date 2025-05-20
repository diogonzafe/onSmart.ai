import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import asyncio
import uuid
import time

from app.orchestration import Orchestrator, get_orchestrator
from app.orchestration.state_manager import AgentState

class TestOrchestrator(unittest.TestCase):
    """Testes para o orquestrador principal."""
    
    def setUp(self):
        """Configura dados de teste."""
        self.mock_db_session = Mock()
        self.mock_graph_builder = Mock()
        self.mock_execution_graph = AsyncMock()
        
        # Configurar o gráfico de execução simulado
        self.mock_graph_builder.create_execution_graph.return_value = self.mock_execution_graph
        
        # Criar o orquestrador com mocks
        with patch('app.orchestration.GraphBuilder', return_value=self.mock_graph_builder):
            self.orchestrator = Orchestrator(self.mock_db_session)
    
    def test_init(self):
        """Testa a inicialização do orquestrador."""
        self.assertEqual(self.orchestrator.db_session, self.mock_db_session)
        self.assertEqual(self.orchestrator.graph_builder, self.mock_graph_builder)
        self.assertEqual(self.orchestrator.execution_graph, self.mock_execution_graph)
    
    async def test_process_message_success(self):
        """Testa o processamento de mensagem com sucesso."""
        conversation_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        message = "Teste de mensagem"
        
        # Simular estado final após processamento
        final_state = AgentState(
            conversation_id=conversation_id,
            user_id=user_id,
            current_message=message
        )
        final_state.add_response(
            agent_response={
                "agent_id": "agent123",
                "content": "Resposta final"
            }
        )
        final_state.processing_times = {"agent123": 0.5, "agent456": 0.3}
        
        # Configurar o mock para retornar o estado final
        self.mock_execution_graph.ainvoke = AsyncMock(return_value=final_state)
        
        # Chamar o método a ser testado
        result = await self.orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message
        )
        
        # Verificar se o grafo foi invocado corretamente
        self.mock_execution_graph.ainvoke.assert_called_once()
        
        # Verificar os elementos da resposta
        self.assertEqual(result["response"], "Resposta final")
        self.assertIn("processing_time", result)
        self.assertEqual(len(result["agent_responses"]), 1)
        self.assertEqual(len(result["agents_involved"]), 2)
        self.assertIn("agent123", result["agents_involved"])
        self.assertIn("agent456", result["agents_involved"])
    
    async def test_process_message_error(self):
        """Testa o processamento de mensagem com erro."""
        conversation_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        message = "Teste de mensagem"
        
        # Simular erro durante o processamento
        self.mock_execution_graph.ainvoke = AsyncMock(side_effect=Exception("Teste de erro"))
        
        # Chamar o método a ser testado
        result = await self.orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message
        )
        
        # Verificar resposta de erro
        self.assertIn("Desculpe, ocorreu um erro", result["response"])
        self.assertIn("processing_time", result)
        self.assertEqual(result["error"], "Teste de erro")
    
    @patch('app.orchestration.Orchestrator')
    def test_get_orchestrator(self, mock_orchestrator_class):
        """Testa a função singleton get_orchestrator."""
        mock_db_session = Mock()
        
        # Resetar o singleton antes do teste
        import app.orchestration
        app.orchestration._orchestrator_instance = None
        
        # Primeira chamada - deve criar uma instância
        orchestrator1 = get_orchestrator(mock_db_session)
        mock_orchestrator_class.assert_called_once_with(mock_db_session)
        
        # Segunda chamada - deve retornar a mesma instância
        orchestrator2 = get_orchestrator(mock_db_session)
        self.assertEqual(mock_orchestrator_class.call_count, 1)
        self.assertEqual(orchestrator1, orchestrator2)

if __name__ == "__main__":
    unittest.main()