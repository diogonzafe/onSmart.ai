import unittest
from datetime import datetime
import json
import uuid

from app.orchestration.state_manager import AgentState, AgentResponse, AgentAction

class TestAgentState(unittest.TestCase):
    """Testes para a classe AgentState."""

    def setUp(self):
        """Configura dados de teste."""
        self.conversation_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        
        self.state = AgentState(
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            current_message="Teste de mensagem"
        )
        
        # Exemplo de resposta
        self.test_response = AgentResponse(
            agent_id="agent123",
            content="Resposta de teste",
            actions=[
                AgentAction(
                    name="test_action",
                    params={"param1": "value1"},
                    agent_id="agent123"
                )
            ],
            confidence=0.9,
            metadata={"test": True}
        )
    
    def test_init(self):
        """Testa a inicialização do estado."""
        self.assertEqual(self.state.conversation_id, self.conversation_id)
        self.assertEqual(self.state.user_id, self.user_id)
        self.assertEqual(self.state.current_message, "Teste de mensagem")
        self.assertEqual(len(self.state.messages), 0)
        self.assertIsNone(self.state.current_agent_id)
        self.assertEqual(len(self.state.responses), 0)
        self.assertEqual(self.state.attempt_count, 0)
        self.assertEqual(self.state.max_attempts, 3)
        self.assertFalse(self.state.is_complete)
        self.assertFalse(self.state.requires_fallback)
    
    def test_add_response(self):
        """Testa a adição de respostas ao estado."""
        # Estado inicial
        self.assertEqual(len(self.state.responses), 0)
        self.assertEqual(len(self.state.actions_history), 0)
        
        # Adicionar resposta
        self.state.add_response(self.test_response)
        
        # Verificar se a resposta foi adicionada
        self.assertEqual(len(self.state.responses), 1)
        self.assertEqual(self.state.responses[0].agent_id, "agent123")
        self.assertEqual(self.state.responses[0].content, "Resposta de teste")
        
        # Verificar se as ações foram registradas
        self.assertEqual(len(self.state.actions_history), 1)
        self.assertEqual(self.state.actions_history[0].name, "test_action")
        self.assertEqual(self.state.actions_history[0].params, {"param1": "value1"})
    
    def test_get_final_response(self):
        """Testa a obtenção da resposta final."""
        # Sem respostas
        self.assertIsNone(self.state.get_final_response())
        
        # Adicionar uma resposta
        self.state.add_response(self.test_response)
        self.assertEqual(self.state.get_final_response(), "Resposta de teste")
        
        # Adicionar uma segunda resposta
        response2 = AgentResponse(
            agent_id="agent456",
            content="Segunda resposta"
        )
        self.state.add_response(response2)
        
        # Deve retornar a resposta mais recente
        self.assertEqual(self.state.get_final_response(), "Segunda resposta")
    
    def test_to_dict_from_dict(self):
        """Testa a conversão entre dicionário e objeto."""
        # Adicionar uma resposta para tornar o estado mais complexo
        self.state.add_response(self.test_response)
        
        # Converter para dicionário
        state_dict = self.state.to_dict()
        
        # Verificar conversão
        self.assertEqual(state_dict["conversation_id"], self.conversation_id)
        self.assertEqual(state_dict["user_id"], self.user_id)
        self.assertEqual(len(state_dict["responses"]), 1)
        
        # Converter de volta para objeto
        new_state = AgentState.from_dict(state_dict)
        
        # Verificar se o objeto reconstruído mantém as propriedades
        self.assertEqual(new_state.conversation_id, self.conversation_id)
        self.assertEqual(new_state.user_id, self.user_id)
        self.assertEqual(len(new_state.responses), 1)
        self.assertEqual(new_state.responses[0].agent_id, "agent123")

class TestAgentAction(unittest.TestCase):
    """Testes para a classe AgentAction."""
    
    def test_init(self):
        """Testa a inicialização de uma ação."""
        action = AgentAction(
            name="test_action",
            params={"param1": "value1"},
            agent_id="agent123"
        )
        
        self.assertEqual(action.name, "test_action")
        self.assertEqual(action.params, {"param1": "value1"})
        self.assertEqual(action.agent_id, "agent123")
        self.assertIsInstance(action.timestamp, datetime)

class TestAgentResponse(unittest.TestCase):
    """Testes para a classe AgentResponse."""
    
    def test_init(self):
        """Testa a inicialização de uma resposta."""
        response = AgentResponse(
            agent_id="agent123",
            content="Resposta de teste",
            actions=[
                AgentAction(
                    name="test_action",
                    params={"param1": "value1"},
                    agent_id="agent123"
                )
            ],
            confidence=0.9,
            metadata={"test": True}
        )
        
        self.assertEqual(response.agent_id, "agent123")
        self.assertEqual(response.content, "Resposta de teste")
        self.assertEqual(len(response.actions), 1)
        self.assertEqual(response.actions[0].name, "test_action")
        self.assertEqual(response.confidence, 0.9)
        self.assertEqual(response.metadata, {"test": True})

if __name__ == "__main__":
    unittest.main()