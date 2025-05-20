import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import uuid

from app.orchestration import Orchestrator
from app.orchestration.state_manager import AgentState

class TestOrchestrationIntegration(unittest.TestCase):
    """Testes de integração para o sistema de orquestração."""
    
    @patch('app.orchestration.graph_builder.supervisor_node')
    @patch('app.orchestration.graph_builder.marketing_node')
    @patch('app.orchestration.graph_builder.fallback_node')
    async def test_full_workflow(self, mock_fallback_node, mock_marketing_node, mock_supervisor_node):
        """Testa o fluxo completo de processamento de uma mensagem."""
        # Configurar mocks para simular o comportamento dos nós
        
        # Nó supervisor direciona para marketing
        async def supervisor_effect(state):
            state.add_response({
                "agent_id": "supervisor123",
                "content": "Direcionando para marketing",
                "metadata": {"selected_department": "marketing"}
            })
            return state
        
        mock_supervisor_node.side_effect = supervisor_effect
        
        # Nó de marketing processa e retorna
        async def marketing_effect(state):
            state.add_response({
                "agent_id": "marketing123",
                "content": "Resposta de marketing",
                "actions": []
            })
            state.is_complete = True
            return state
        
        mock_marketing_node.side_effect = marketing_effect
        
        # Fallback não deve ser chamado neste fluxo
        mock_fallback_node.side_effect = AsyncMock()
        
        # Criar orquestrador com mocks
        orchestrator = Orchestrator(Mock())
        
        # Processar uma mensagem
        conversation_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        message = "Preciso de ajuda com estratégia de redes sociais"
        
        result = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message
        )
        
        # Verificar resultado
        self.assertEqual(result["response"], "Resposta de marketing")
        self.assertGreaterEqual(len(result["agent_responses"]), 2)  # Supervisor e Marketing
        
        # Verificar ordem de chamadas
        self.assertEqual(mock_supervisor_node.call_count, 1)
        self.assertEqual(mock_marketing_node.call_count, 1)
        self.assertEqual(mock_fallback_node.call_count, 0)  # Não deve ser chamado
    
    @patch('app.orchestration.graph_builder.supervisor_node')
    @patch('app.orchestration.graph_builder.marketing_node')
    @patch('app.orchestration.graph_builder.fallback_node')
    async def test_fallback_workflow(self, mock_fallback_node, mock_marketing_node, mock_supervisor_node):
        """Testa o fluxo de fallback quando o marketing falha."""
        # Configurar mocks para simular o comportamento dos nós
        
        # Nó supervisor direciona para marketing
        async def supervisor_effect(state):
            if state.requires_fallback:
                # Segunda chamada após fallback
                state.is_complete = True
                return state
                
            # Primeira chamada
            state.add_response({
                "agent_id": "supervisor123",
                "content": "Direcionando para marketing",
                "metadata": {"selected_department": "marketing"}
            })
            return state
        
        mock_supervisor_node.side_effect = supervisor_effect
        
        # Nó de marketing falha
        async def marketing_effect(state):
            state.requires_fallback = True
            return state
        
        mock_marketing_node.side_effect = marketing_effect
        
        # Nó de fallback responde
        async def fallback_effect(state):
            state.add_response({
                "agent_id": "fallback_system",
                "content": "Resposta de fallback",
                "metadata": {"fallback": True}
            })
            return state
        
        mock_fallback_node.side_effect = fallback_effect
        
        # Criar orquestrador com mocks
        orchestrator = Orchestrator(Mock())
        
        # Processar uma mensagem
        conversation_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        message = "Mensagem que causará falha"
        
        result = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message
        )
        
        # Verificar resultado
        self.assertEqual(result["response"], "Resposta de fallback")
        
        # Verificar ordem de chamadas
        self.assertGreaterEqual(mock_supervisor_node.call_count, 1)
        self.assertEqual(mock_marketing_node.call_count, 1)
        self.assertEqual(mock_fallback_node.call_count, 1)

if __name__ == "__main__":
    unittest.main()