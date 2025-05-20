import unittest
import uuid

from app.orchestration.state_manager import AgentState, AgentResponse
from app.orchestration.routing_logic import route_to_department, should_end

class TestRoutingLogic(unittest.TestCase):
    """Testes para a lógica de roteamento entre nós."""
    
    def setUp(self):
        """Configura dados de teste."""
        self.conversation_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        
        self.state = AgentState(
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            current_message="Teste de mensagem"
        )
    
    def test_route_to_department_complete(self):
        """Testa o roteamento quando o fluxo está completo."""
        # Configurar estado
        self.state.is_complete = True
        
        # Verificar roteamento
        result = route_to_department(self.state)
        self.assertEqual(result, "complete")
    
    def test_route_to_department_fallback(self):
        """Testa o roteamento quando fallback é necessário."""
        # Configurar estado
        self.state.requires_fallback = True
        
        # Verificar roteamento
        result = route_to_department(self.state)
        self.assertEqual(result, "fallback")
    
    def test_route_to_department_marketing(self):
        """Testa o roteamento para marketing."""
        # Configurar estado com resposta
        response = AgentResponse(
            agent_id="supervisor123",
            content="Resposta do supervisor",
            metadata={"selected_department": "marketing"}
        )
        self.state.add_response(response)
        
        # Verificar roteamento
        result = route_to_department(self.state)
        self.assertEqual(result, "marketing")
    
    def test_route_to_department_default(self):
        """Testa o roteamento padrão quando nenhuma condição é atendida."""
        # Estado sem respostas ou com departamento não reconhecido
        result = route_to_department(self.state)
        self.assertEqual(result, "fallback")
        
        # Adicionar resposta sem metadados de departamento
        response = AgentResponse(
            agent_id="supervisor123",
            content="Resposta do supervisor",
            metadata={}
        )
        self.state.add_response(response)
        
        # Verificar que ainda vai para fallback
        result = route_to_department(self.state)
        self.assertEqual(result, "fallback")
    
    def test_should_end_explicit(self):
        """Testa a condição de término explícita."""
        # Configurar estado
        self.state.is_complete = True
        
        # Verificar condição
        self.assertTrue(should_end(self.state))
    
    def test_should_end_max_attempts(self):
        """Testa a condição de término por número máximo de tentativas."""
        # Configurar estado
        self.state.attempt_count = 3
        self.state.max_attempts = 3
        
        # Verificar condição
        self.assertTrue(should_end(self.state))
    
    def test_should_end_continue(self):
        """Testa quando o fluxo deve continuar."""
        # Estado padrão
        self.assertFalse(should_end(self.state))
        
        # Com algumas tentativas, mas abaixo do máximo
        self.state.attempt_count = 2
        self.state.max_attempts = 3
        self.assertFalse(should_end(self.state))

if __name__ == "__main__":
    unittest.main()