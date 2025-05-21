# Novo arquivo app/tests/test_orchestration/test_complete_workflow.py

import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import uuid

from app.orchestration import Orchestrator
from app.orchestration.state_manager import AgentState, AgentResponse
from app.models.agent import AgentType

# Função auxiliar para executar coroutines nos testes
def executar_async(coro):
    """Auxiliar para executar testes assíncronos."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

class TestCompleteWorkflow(unittest.TestCase):
    """Testes para o fluxo de trabalho completo com todos os departamentos."""
    
    @patch('app.orchestration.graph_builder.supervisor_node')
    @patch('app.orchestration.graph_builder.marketing_node')
    @patch('app.orchestration.graph_builder.sales_node')
    @patch('app.orchestration.graph_builder.finance_node')
    @patch('app.orchestration.graph_builder.fallback_node')
    def test_marketing_workflow(self, mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor):
        """Testa o fluxo completo para o departamento de marketing."""
        return executar_async(self._test_marketing_workflow(
            mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor))
    
    async def _test_marketing_workflow(self, mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor):
        """Implementação assíncrona do teste para o departamento de marketing."""
        # Configurar o comportamento do supervisor para direcionar para marketing
        async def supervisor_effect(state):
            state.add_response(AgentResponse(
                agent_id="supervisor123",
                content="Direcionando para marketing",
                metadata={"selected_department": "marketing"}
            ))
            return state
        
        mock_supervisor.side_effect = supervisor_effect
        
        # Configurar o comportamento do nó de marketing
        async def marketing_effect(state):
            state.add_response(AgentResponse(
                agent_id="marketing123",
                content="Resposta de marketing sobre redes sociais",
                actions=[]
            ))
            state.is_complete = True
            return state
        
        mock_marketing.side_effect = marketing_effect
        
        # Os outros nós não devem ser chamados
        mock_sales.side_effect = AsyncMock()
        mock_finance.side_effect = AsyncMock()
        mock_fallback.side_effect = AsyncMock()
        
        # Criar orquestrador
        orchestrator = Orchestrator(Mock())
        
        # Processar uma mensagem de marketing
        conversation_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        message = "Preciso de ajuda com uma campanha de marketing nas redes sociais"
        
        result = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message
        )
        
        # Verificar resultado
        self.assertEqual(result["response"], "Resposta de marketing sobre redes sociais")
        self.assertEqual(mock_marketing.call_count, 1)
        self.assertEqual(mock_sales.call_count, 0)
        self.assertEqual(mock_finance.call_count, 0)
        self.assertEqual(mock_fallback.call_count, 0)
    
    @patch('app.orchestration.graph_builder.supervisor_node')
    @patch('app.orchestration.graph_builder.marketing_node')
    @patch('app.orchestration.graph_builder.sales_node')
    @patch('app.orchestration.graph_builder.finance_node')
    @patch('app.orchestration.graph_builder.fallback_node')
    def test_sales_workflow(self, mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor):
        """Testa o fluxo completo para o departamento de vendas."""
        return executar_async(self._test_sales_workflow(
            mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor))
    
    async def _test_sales_workflow(self, mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor):
        """Implementação assíncrona do teste para o departamento de vendas."""
        # Configurar o comportamento do supervisor para direcionar para vendas
        async def supervisor_effect(state):
            state.add_response(AgentResponse(
                agent_id="supervisor123",
                content="Direcionando para vendas",
                metadata={"selected_department": "sales"}
            ))
            return state
        
        mock_supervisor.side_effect = supervisor_effect
        
        # Configurar o comportamento do nó de vendas
        async def sales_effect(state):
            state.add_response(AgentResponse(
                agent_id="sales123",
                content="Resposta de vendas sobre proposta comercial",
                actions=[]
            ))
            state.is_complete = True
            return state
        
        mock_sales.side_effect = sales_effect
        
        # Os outros nós não devem ser chamados
        mock_marketing.side_effect = AsyncMock()
        mock_finance.side_effect = AsyncMock()
        mock_fallback.side_effect = AsyncMock()
        
        # Criar orquestrador
        orchestrator = Orchestrator(Mock())
        
        # Processar uma mensagem de vendas
        conversation_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        message = "Preciso negociar uma proposta comercial para um novo cliente"
        
        result = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message
        )
        
        # Verificar resultado
        self.assertEqual(result["response"], "Resposta de vendas sobre proposta comercial")
        self.assertEqual(mock_marketing.call_count, 0)
        self.assertEqual(mock_sales.call_count, 1)
        self.assertEqual(mock_finance.call_count, 0)
        self.assertEqual(mock_fallback.call_count, 0)
    
    @patch('app.orchestration.graph_builder.supervisor_node')
    @patch('app.orchestration.graph_builder.marketing_node')
    @patch('app.orchestration.graph_builder.sales_node')
    @patch('app.orchestration.graph_builder.finance_node')
    @patch('app.orchestration.graph_builder.fallback_node')
    def test_finance_workflow(self, mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor):
        """Testa o fluxo completo para o departamento de finanças."""
        return executar_async(self._test_finance_workflow(
            mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor))
    
    async def _test_finance_workflow(self, mock_fallback, mock_finance, mock_sales, mock_marketing, mock_supervisor):
        """Implementação assíncrona do teste para o departamento de finanças."""
        # Configurar o comportamento do supervisor para direcionar para finanças
        async def supervisor_effect(state):
            state.add_response(AgentResponse(
                agent_id="supervisor123",
                content="Direcionando para finanças",
                metadata={"selected_department": "finance"}
            ))
            return state
        
        mock_supervisor.side_effect = supervisor_effect
        
        # Configurar o comportamento do nó de finanças
        async def finance_effect(state):
            state.add_response(AgentResponse(
                agent_id="finance123",
                content="Resposta de finanças sobre análise orçamentária",
                actions=[]
            ))
            state.is_complete = True
            return state
        
        mock_finance.side_effect = finance_effect
        
        # Os outros nós não devem ser chamados
        mock_marketing.side_effect = AsyncMock()
        mock_sales.side_effect = AsyncMock()
        mock_fallback.side_effect = AsyncMock()
        
        # Criar orquestrador
        orchestrator = Orchestrator(Mock())
        
        # Processar uma mensagem de finanças
        conversation_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        message = "Preciso analisar o orçamento do próximo trimestre"
        
        result = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message
        )
        
        # Verificar resultado
        self.assertEqual(result["response"], "Resposta de finanças sobre análise orçamentária")
        self.assertEqual(mock_marketing.call_count, 0)
        self.assertEqual(mock_sales.call_count, 0)
        self.assertEqual(mock_finance.call_count, 1)
        self.assertEqual(mock_fallback.call_count, 0)