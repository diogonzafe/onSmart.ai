import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import asyncio
import uuid

from app.orchestration.state_manager import AgentState, AgentResponse, AgentAction
from app.orchestration.node_functions import supervisor_node, marketing_node, fallback_node
from app.models.agent import AgentType

class TestNodeFunctions(unittest.TestCase):
    """Testes para as funções de nó do grafo."""

    def setUp(self):
        """Configura dados de teste."""
        self.conversation_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        
        self.state = AgentState(
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            current_message="Teste de mensagem"
        )
    
    @patch('app.orchestration.node_functions.get_agent_service')
    @patch('app.orchestration.node_functions.create_agent')
    async def test_supervisor_node(self, mock_create_agent, mock_get_service):
        """Testa o nó do supervisor."""
        # Configurar mocks
        mock_agent_service = AsyncMock()
        mock_get_service.return_value = mock_agent_service
        
        mock_supervisor_agent = Mock()
        mock_agent_record = Mock(id="supervisor123")
        mock_agent_service.list_agents.return_value = [mock_agent_record]
        
        mock_create_agent.return_value = mock_supervisor_agent
        
        # Simular resposta do agente
        mock_response = {
            "message": {
                "id": "msg123",
                "content": "Resposta do supervisor"
            },
            "metadata": {
                "selected_department": "marketing"
            }
        }
        mock_supervisor_agent.process_message = AsyncMock(return_value=mock_response)
        
        # Chamar a função a ser testada
        result_state = await supervisor_node(self.state)
        
        # Verificar se o agente foi criado corretamente
        mock_agent_service.list_agents.assert_called_once_with(
            user_id=self.user_id,
            agent_type=AgentType.SUPERVISOR,
            is_active=True
        )
        
        mock_create_agent.assert_called_once_with(
            agent_type=AgentType.SUPERVISOR,
            db=None,
            agent_record=mock_agent_record
        )
        
        # Verificar se o agente processou a mensagem
        mock_supervisor_agent.process_message.assert_called_once_with(
            conversation_id=self.conversation_id,
            message=self.state.current_message
        )
        
        # Verificar atualizações no estado
        self.assertEqual(len(result_state.responses), 1)
        self.assertEqual(result_state.responses[0].agent_id, "supervisor123")
        self.assertEqual(result_state.responses[0].content, "Resposta do supervisor")
        self.assertEqual(result_state.current_agent_id, "supervisor123")
        self.assertEqual(result_state.next_agent_id, "marketing")
        self.assertFalse(result_state.is_complete)
    
    @patch('app.orchestration.node_functions.get_agent_service')
    @patch('app.orchestration.node_functions.create_agent')
    async def test_marketing_node(self, mock_create_agent, mock_get_service):
        """Testa o nó de marketing."""
        # Configurar mocks
        mock_agent_service = AsyncMock()
        mock_get_service.return_value = mock_agent_service
        
        mock_marketing_agent = Mock()
        mock_agent_record = Mock(id="marketing123")
        mock_agent_service.list_agents.return_value = [mock_agent_record]
        
        mock_create_agent.return_value = mock_marketing_agent
        
        # Simular resposta do agente
        mock_response = {
            "message": {
                "id": "msg456",
                "content": "Resposta do marketing"
            },
            "actions": [
                {"name": "analyze_audience", "params": {"segment": "millennials"}}
            ],
            "metadata": {}
        }
        mock_marketing_agent.process_message = AsyncMock(return_value=mock_response)
        
        # Definir agente atual
        self.state.current_agent_id = "supervisor123"
        
        # Chamar a função a ser testada
        result_state = await marketing_node(self.state)
        
        # Verificar se o agente foi criado corretamente
        mock_agent_service.list_agents.assert_called_once_with(
            user_id=self.user_id,
            agent_type=AgentType.MARKETING,
            is_active=True
        )
        
        mock_create_agent.assert_called_once_with(
            agent_type=AgentType.MARKETING,
            db=None,
            agent_record=mock_agent_record
        )
        
        # Verificar se o agente processou a mensagem
        mock_marketing_agent.process_message.assert_called_once_with(
            conversation_id=self.conversation_id,
            message=self.state.current_message
        )
        
        # Verificar atualizações no estado
        self.assertEqual(len(result_state.responses), 1)
        self.assertEqual(result_state.responses[0].agent_id, "marketing123")
        self.assertEqual(result_state.responses[0].content, "Resposta do marketing")
        self.assertEqual(result_state.previous_agent_id, "supervisor123")
        self.assertEqual(result_state.current_agent_id, "marketing123")
        self.assertEqual(result_state.attempt_count, 1)
        self.assertFalse(result_state.is_complete)
        self.assertFalse(result_state.requires_fallback)
    
    @patch('app.orchestration.node_functions.get_agent_service')
    @patch('app.orchestration.node_functions.create_agent')
    async def test_marketing_node_error(self, mock_create_agent, mock_get_service):
        """Testa o nó de marketing com erro."""
        # Configurar mocks
        mock_agent_service = AsyncMock()
        mock_get_service.return_value = mock_agent_service
        
        mock_marketing_agent = Mock()
        mock_agent_record = Mock(id="marketing123")
        mock_agent_service.list_agents.return_value = [mock_agent_record]
        
        mock_create_agent.return_value = mock_marketing_agent
        
        # Simular erro do agente
        mock_marketing_agent.process_message = AsyncMock(side_effect=Exception("Teste de erro"))
        
        # Chamar a função a ser testada
        result_state = await marketing_node(self.state)
        
        # Verificar que o estado indica fallback necessário
        self.assertTrue(result_state.requires_fallback)
    
    async def test_fallback_node(self):
        """Testa o nó de fallback."""
        # Definir agente atual
        self.state.current_agent_id = "marketing123"
        
        # Chamar a função a ser testada
        result_state = await fallback_node(self.state)
        
        # Verificar atualizações no estado
        self.assertEqual(len(result_state.responses), 1)
        self.assertEqual(result_state.previous_agent_id, "marketing123")
        self.assertEqual(result_state.current_agent_id, "fallback_system")
        self.assertTrue(result_state.is_complete)
        
        # Verificar resposta de fallback
        self.assertIn("Não foi possível processar sua solicitação", result_state.responses[0].content)

if __name__ == "__main__":
    unittest.main()