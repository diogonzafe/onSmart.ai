# app/tests/test_supervisor_routing_corrected.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.orchestration.node_functions import _analyze_message_for_department
from app.orchestration.state_manager import AgentState, AgentResponse
from app.models.agent import AgentType


class TestDepartmentAnalysis:
    """
    Testes simples para validar a análise de departamento corrigida.
    """
    
    def test_marketing_keywords(self):
        """Testa identificação de palavras-chave de marketing."""
        
        marketing_messages = [
            "Como posso melhorar minha campanha de marketing digital?",
            "Preciso de estratégias para redes sociais",
            "Análise de engajamento no Instagram",
            "Como aumentar o alcance no LinkedIn?",
            "Planejamento de conteúdo para blog",
            "Estratégia de branding para startup",
            "Criação de posts no Facebook"
        ]
        
        for message in marketing_messages:
            result = _analyze_message_for_department(message)
            print(f"Marketing test: '{message}' → {result}")
            assert result == "marketing", f"Mensagem '{message}' deveria ser marketing, mas retornou '{result}'"
    
    def test_sales_keywords(self):
        """Testa identificação de palavras-chave de vendas."""
        
        sales_messages = [
            "Como melhorar o pipeline de vendas?",
            "Estratégias para conversão de leads",
            "Processo de qualificação de prospects",
            "Como qualificar prospects melhor?",
            "CRM para gestão de oportunidades",
            "Técnicas de fechamento de vendas",
            "Follow-up com clientes potenciais",
            "Gestão de relacionamento com clientes"
        ]
        
        for message in sales_messages:
            result = _analyze_message_for_department(message)
            print(f"Sales test: '{message}' → {result}")
            assert result == "sales", f"Mensagem '{message}' deveria ser sales, mas retornou '{result}'"
    
    def test_finance_keywords(self):
        """Testa identificação de palavras-chave financeiras."""
        
        finance_messages = [
            "Análise do fluxo de caixa da empresa",
            "Como calcular o ROI do projeto?",
            "Planejamento orçamentário para 2025",
            "Controle de custos operacionais",
            "Demonstrativo financeiro mensal",
            "Análise de viabilidade do investimento",
            "Indicadores financeiros principais",
            "Relatório de receitas e despesas"
        ]
        
        for message in finance_messages:
            result = _analyze_message_for_department(message)
            print(f"Finance test: '{message}' → {result}")
            assert result == "finance", f"Mensagem '{message}' deveria ser finance, mas retornou '{result}'"
    
    def test_ambiguous_messages(self):
        """Testa mensagens ambíguas."""
        
        ambiguous_messages = [
            "Olá",
            "Ajuda",
            "Como posso melhorar?",
            "Preciso de apoio",
            "???",
            ""
        ]
        
        for message in ambiguous_messages:
            result = _analyze_message_for_department(message)
            print(f"Ambiguous test: '{message}' → {result}")
            # Para mensagens ambíguas, qualquer departamento é válido
            assert result in ["marketing", "sales", "finance"]
    
    def test_mixed_messages(self):
        """Testa mensagens que misturam departamentos."""
        
        mixed_message = "Análise do ROI das campanhas de marketing e impacto nas vendas"
        result = _analyze_message_for_department(mixed_message)
        print(f"Mixed test: '{mixed_message}' → {result}")
        
        # Para mensagens mistas, esperamos que pelo menos identifique um dos departamentos
        assert result in ["marketing", "sales", "finance"]


class TestSupervisorNodeSimple:
    """
    Testes simplificados para o nó supervisor.
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
            current_message="Como melhorar minha estratégia de marketing?",
            messages=[],
            db_session=mock_db_session
        )
    
    def test_state_creation(self, agent_state):
        """Testa se o estado é criado corretamente."""
        assert agent_state.conversation_id == "test-conversation-123"
        assert agent_state.user_id == "test-user-456"
        assert agent_state.current_message == "Como melhorar minha estratégia de marketing?"
        assert len(agent_state.responses) == 0
        assert not agent_state.is_complete
    
    def test_department_analysis_integration(self):
        """Testa a integração da análise de departamento."""
        
        test_cases = [
            ("Campanha de marketing digital", "marketing"),
            ("Pipeline de vendas", "sales"),
            ("Fluxo de caixa", "finance"),
            ("Análise de ROI", "finance"),
            ("Gestão de leads", "sales"),
            ("Estratégia de conteúdo", "marketing")
        ]
        
        for message, expected_dept in test_cases:
            result = _analyze_message_for_department(message)
            print(f"Integration test: '{message}' → {result} (expected: {expected_dept})")
            assert result == expected_dept


# Teste de função isolada para debug
def test_individual_keywords():
    """Teste individual de palavras-chave específicas."""
    
    # Teste palavras específicas que estavam falhando
    test_cases = [
        ("Como qualificar prospects melhor?", "sales"),
        ("Análise do fluxo de caixa da empresa", "finance"),
        ("Gestão de pipeline de vendas", "sales"),
        ("Controle financeiro", "finance"),
        ("Campanha de marketing", "marketing"),
        ("leads", "sales"),
        ("prospects", "sales"),
        ("qualificar", "sales"),
        ("fluxo de caixa", "finance"),
        ("orçamento", "finance"),
        ("roi", "finance")
    ]
    
    print("\n=== TESTE INDIVIDUAL DE PALAVRAS-CHAVE ===")
    for message, expected in test_cases:
        result = _analyze_message_for_department(message)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{message}' → {result} (esperado: {expected})")
        
        if result != expected:
            print(f"   FALHA: Era esperado '{expected}' mas obteve '{result}'")


if __name__ == "__main__":
    # Executar teste individual
    test_individual_keywords()
    
    # Executar testes de classe
    test_class = TestDepartmentAnalysis()
    
    print("\n=== TESTANDO MARKETING ===")
    try:
        test_class.test_marketing_keywords()
        print("✅ Marketing keywords - PASSOU")
    except Exception as e:
        print(f"❌ Marketing keywords - FALHOU: {e}")
    
    print("\n=== TESTANDO SALES ===")
    try:
        test_class.test_sales_keywords()
        print("✅ Sales keywords - PASSOU")
    except Exception as e:
        print(f"❌ Sales keywords - FALHOU: {e}")
    
    print("\n=== TESTANDO FINANCE ===")
    try:
        test_class.test_finance_keywords()
        print("✅ Finance keywords - PASSOU")
    except Exception as e:
        print(f"❌ Finance keywords - FALHOU: {e}")
    
    print("\n=== TESTANDO MENSAGENS AMBÍGUAS ===")
    try:
        test_class.test_ambiguous_messages()
        print("✅ Ambiguous messages - PASSOU")
    except Exception as e:
        print(f"❌ Ambiguous messages - FALHOU: {e}")