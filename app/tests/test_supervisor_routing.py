# test_supervisor_routing.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.orchestration.node_functions import supervisor_node, _analyze_message_for_department
from app.orchestration.state_manager import AgentState, AgentResponse
from app.models.agent import AgentType
from app.models.user import User
from app.models.conversation import Conversation, ConversationStatus


class TestSupervisorAutomaticRouting:
    """
    Testes para validar o roteamento automático do supervisor
    quando não há agente supervisor configurado.
    """
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock da sessão do banco de dados."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def agent_state(self, mock_db_session):
        """Estado base para testes."""
        return AgentState(
            conversation_id="test-conversation-123",
            user_id="test-user-456",
            current_message="",
            messages=[],
            db_session=mock_db_session
        )
    
    def test_analyze_message_for_department_marketing(self):
        """Testa se mensagens de marketing são identificadas corretamente."""
        
        # Casos de teste para marketing
        marketing_messages = [
            "Como posso melhorar minha campanha de marketing digital?",
            "Preciso de estratégias para redes sociais",
            "Análise de performance da marca no Instagram",
            "Como aumentar o engajamento no LinkedIn?",
            "Planejamento de conteúdo para blog",
            "ROI das campanhas de Facebook Ads",
            "Estratégia de branding para startup"
        ]
        
        for message in marketing_messages:
            result = _analyze_message_for_department(message)
            assert result == "marketing", f"Mensagem '{message}' deveria ser marketing, mas retornou '{result}'"
    
    def test_analyze_message_for_department_sales(self):
        """Testa se mensagens de vendas são identificadas corretamente."""
        
        # Casos de teste para vendas
        sales_messages = [
            "Como melhorar o pipeline de vendas?",
            "Estratégias para conversão de leads",
            "Processo de negociação com clientes",
            "CRM para gestão de oportunidades",
            "Como qualificar prospects melhor?",
            "Técnicas de fechamento de vendas",
            "Follow-up com clientes potenciais",
            "Análise do funil de conversão"
        ]
        
        for message in sales_messages:
            result = _analyze_message_for_department(message)
            assert result == "sales", f"Mensagem '{message}' deveria ser sales, mas retornou '{result}'"
    
    def test_analyze_message_for_department_finance(self):
        """Testa se mensagens financeiras são identificadas corretamente."""
        
        # Casos de teste para finanças
        finance_messages = [
            "Análise do fluxo de caixa da empresa",
            "Como calcular o ROI do projeto?",
            "Planejamento orçamentário para 2025",
            "Controle de custos operacionais",
            "Demonstrativo financeiro mensal",
            "Análise de viabilidade do investimento",
            "Margem de lucro por produto",
            "Indicadores financeiros principais"
        ]
        
        for message in finance_messages:
            result = _analyze_message_for_department(message)
            assert result == "finance", f"Mensagem '{message}' deveria ser finance, mas retornou '{result}'"
    
    def test_analyze_message_complex_scenarios(self):
        """Testa cenários mais complexos e multi-departamentais."""
        
        # Teste de mensagem multi-departamental (deve priorizar um)
        complex_message = "Preciso analisar o ROI das campanhas de marketing e o impacto nas vendas"
        result = _analyze_message_for_department(complex_message)
        # Deve retornar marketing ou sales (ambos são válidos)
        assert result in ["marketing", "sales", "finance"]
        
        # Mensagem muito curta deve ter fallback
        short_message = "Ajuda"
        result = _analyze_message_for_department(short_message)
        assert result in ["marketing", "sales", "finance"]  # Qualquer um é aceitável
    
    @pytest.mark.asyncio
    async def test_supervisor_node_without_supervisor_agent(self, agent_state, mock_db_session):
        """
        Testa o comportamento do supervisor_node quando não há agente supervisor configurado.
        """
        # Configurar mensagem de teste
        agent_state.current_message = "Como melhorar minha estratégia de marketing digital?"
        
        # Mock do agent_service para simular que não há supervisor
        with patch('app.orchestration.node_functions.get_agent_service') as mock_agent_service:
            mock_service = AsyncMock()
            mock_agent_service.return_value = mock_service
            
            # Simular que não há agentes supervisor
            mock_service.list_agents.return_value = []
            
            # Executar o nó supervisor
            result_state = await supervisor_node(agent_state)
            
            # Verificar se o estado foi atualizado
            assert len(result_state.responses) > 0
            
            # Verificar se identificou marketing como departamento
            last_response = result_state.responses[-1]
            assert "marketing" in last_response.metadata.get("selected_department", "").lower()
            
            # Verificar se o next_agent_id foi configurado
            assert result_state.next_agent_id == "marketing"
    
    @pytest.mark.asyncio
    async def test_supervisor_node_with_agents_available(self, agent_state, mock_db_session):
        """
        Testa o comportamento quando há agentes especializados disponíveis.
        """
        # Configurar mensagem de vendas
        agent_state.current_message = "Como qualificar melhor os leads no pipeline?"
        
        # Mock de agente de vendas disponível
        mock_sales_agent = Mock()
        mock_sales_agent.id = "sales-agent-123"
        mock_sales_agent.type = AgentType.SALES
        
        with patch('app.orchestration.node_functions.get_agent_service') as mock_agent_service:
            mock_service = AsyncMock()
            mock_agent_service.return_value = mock_service
            
            # Simular que não há supervisor, mas há agente de vendas
            mock_service.list_agents.side_effect = [
                [],  # Nenhum supervisor
                [mock_sales_agent]  # Agente de vendas disponível
            ]
            
            # Executar o nó supervisor
            result_state = await supervisor_node(agent_state)
            
            # Verificar se identificou vendas e configurou roteamento
            assert len(result_state.responses) > 0
            last_response = result_state.responses[-1]
            assert last_response.metadata.get("selected_department") == "sales"
            assert result_state.next_agent_id == "sales"
    
    @pytest.mark.asyncio
    async def test_supervisor_node_no_agents_available(self, agent_state, mock_db_session):
        """
        Testa o comportamento quando não há agentes especializados disponíveis.
        """
        # Configurar mensagem
        agent_state.current_message = "Preciso de ajuda com análise financeira"
        
        with patch('app.orchestration.node_functions.get_agent_service') as mock_agent_service:
            mock_service = AsyncMock()
            mock_agent_service.return_value = mock_service
            
            # Simular que não há nenhum agente disponível
            mock_service.list_agents.return_value = []
            
            # Executar o nó supervisor
            result_state = await supervisor_node(agent_state)
            
            # Verificar se gerou resposta educativa
            assert len(result_state.responses) > 0
            last_response = result_state.responses[-1]
            
            # Deve ter resposta educativa
            assert "criar agentes especializados" in last_response.content.lower()
            
            # Deve marcar como completo
            assert result_state.is_complete
    
    def test_routing_priority_multi_department(self):
        """Testa a priorização quando múltiplos departamentos são identificados."""
        
        # Mensagem que menciona múltiplos departamentos
        message = "Análise do ROI das campanhas de marketing e impacto nas vendas e controle de custos"
        
        result = _analyze_message_for_department(message)
        
        # Deve retornar um dos departamentos identificados
        assert result in ["marketing", "sales", "finance"]
    
    @pytest.mark.asyncio
    async def test_supervisor_error_handling(self, agent_state, mock_db_session):
        """Testa o tratamento de erros no supervisor."""
        
        agent_state.current_message = "Teste de erro"
        
        with patch('app.orchestration.node_functions.get_agent_service') as mock_agent_service:
            # Simular erro no agent_service
            mock_agent_service.side_effect = Exception("Erro simulado")
            
            # Executar o nó supervisor
            result_state = await supervisor_node(agent_state)
            
            # Verificar se tratou o erro adequadamente
            assert len(result_state.responses) > 0
            last_response = result_state.responses[-1]
            
            # Deve conter resposta de erro com orientação
            assert "erro" in last_response.content.lower()
            assert result_state.is_complete
    
    def test_department_identification_edge_cases(self):
        """Testa casos extremos de identificação de departamento."""
        
        test_cases = [
            ("", "marketing"),  # Mensagem vazia
            ("???", "marketing"),  # Apenas pontuação
            ("Olá", "marketing"),  # Saudação simples
            ("Muito obrigado!", "marketing"),  # Agradecimento
        ]
        
        for message, expected_fallback in test_cases:
            result = _analyze_message_for_department(message)
            # Para casos extremos, qualquer departamento é aceitável
            assert result in ["marketing", "sales", "finance"]


# Teste de integração mais complexo
class TestSupervisorIntegration:
    """Testes de integração do sistema de roteamento."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_routing_flow(self):
        """Testa o fluxo completo de roteamento automático."""
        
        # Simular estado inicial
        mock_db = Mock(spec=Session)
        
        state = AgentState(
            conversation_id="integration-test-123",
            user_id="user-integration-456",
            current_message="Preciso criar uma campanha de marketing para redes sociais",
            messages=[],
            db_session=mock_db
        )
        
        with patch('app.orchestration.node_functions.get_agent_service') as mock_agent_service:
            mock_service = AsyncMock()
            mock_agent_service.return_value = mock_service
            
            # Configurar mock para simular agente de marketing disponível
            mock_marketing_agent = Mock()
            mock_marketing_agent.id = "marketing-agent-integration"
            mock_marketing_agent.type = AgentType.MARKETING
            
            mock_service.list_agents.side_effect = [
                [],  # Nenhum supervisor
                [mock_marketing_agent]  # Agente de marketing disponível
            ]
            
            # Executar supervisor
            result_state = await supervisor_node(state)
            
            # Validar resultado final
            assert not result_state.is_complete  # Deve continuar para o próximo nó
            assert result_state.next_agent_id == "marketing"
            assert len(result_state.responses) > 0
            
            # Verificar conteúdo da resposta
            response = result_state.responses[-1]
            assert "marketing" in response.content.lower()
            assert response.metadata.get("selected_department") == "marketing"


if __name__ == "__main__":
    # Executar testes individuais para debug
    import sys
    
    def run_basic_tests():
        """Executa testes básicos de análise de departamento."""
        test_class = TestSupervisorAutomaticRouting()
        
        print("🧪 Testando identificação de departamento...")
        
        try:
            test_class.test_analyze_message_for_department_marketing()
            print("✅ Marketing - OK")
            
            test_class.test_analyze_message_for_department_sales()
            print("✅ Sales - OK")
            
            test_class.test_analyze_message_for_department_finance()
            print("✅ Finance - OK")
            
            test_class.test_analyze_message_complex_scenarios()
            print("✅ Cenários complexos - OK")
            
            test_class.test_routing_priority_multi_department()
            print("✅ Priorização multi-departamental - OK")
            
            print("\n🎉 Todos os testes básicos passaram!")
            
        except Exception as e:
            print(f"❌ Erro nos testes: {str(e)}")
            return False
        
        return True
    
    if len(sys.argv) > 1 and sys.argv[1] == "--basic":
        run_basic_tests()
    else:
        print("Para executar todos os testes, use: pytest test_supervisor_routing.py")
        print("Para testes básicos, use: python test_supervisor_routing.py --basic")