# tests/test_agent_state.py
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from app.agents.base import AgentState
from app.services.conversation_service import ConversationService
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole

class TestEnhancedAgentState:
    @pytest.fixture
    def agent_state(self):
        """Fixture para estado de agente aprimorado."""
        return AgentState()
    
    def test_initial_status(self, agent_state):
        """Testa o estado inicial do agente."""
        assert agent_state.status == AgentState.READY
        assert agent_state.error is None
        assert len(agent_state.state_history) == 0
    
    def test_update_status(self, agent_state):
        """Testa a atualização de status com histórico."""
        # Atualizar status
        agent_state.update_status(AgentState.PROCESSING)
        
        # Verificar resultado
        assert agent_state.status == AgentState.PROCESSING
        assert len(agent_state.state_history) == 1
        assert agent_state.state_history[0]["from_status"] == AgentState.READY
        assert agent_state.state_history[0]["to_status"] == AgentState.PROCESSING
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, agent_state):
        """Testa o sistema de heartbeat."""
        # Verificar estado inicial
        assert agent_state.is_alive() == True
        
        # Simular delay no heartbeat (maior que o intervalo)
        agent_state.last_heartbeat = datetime.utcnow() - timedelta(seconds=agent_state.heartbeat_interval * 3)
        assert agent_state.is_alive() == False
        
        # Enviar heartbeat
        await agent_state.send_heartbeat()
        assert agent_state.is_alive() == True
    
    def test_can_process_request(self, agent_state):
        """Testa verificação de disponibilidade para processar solicitações."""
        # Estados que permitem processamento
        assert agent_state.can_process_request() == True  # READY é o estado inicial
        
        # Mudar para estado que não permite processamento
        agent_state.update_status(AgentState.PROCESSING)
        assert agent_state.can_process_request() == False
        
        # Mudar para estado que permite processamento
        agent_state.update_status(AgentState.COMPLETED)
        assert agent_state.can_process_request() == True

class TestConversationService:
    @pytest.fixture
    def conversation_service(self):
        """Fixture para o serviço de conversas."""
        db = MagicMock()
        agent_service = MagicMock()
        
        service = ConversationService(db)
        service.agent_service = agent_service
        
        return service
    
    @pytest.mark.asyncio
    async def test_resume_conversation(self, conversation_service):
        """Testa a retomada de uma conversa."""
        # Mock para conversa
        conversation = MagicMock(spec=Conversation)
        conversation.id = "conv-123"
        conversation.agent_id = "agent-123"
        conversation.status = ConversationStatus.ACTIVE
        
        # Mock para agente
        agent = MagicMock()
        agent.id = "agent-123"
        
        # Mock para mensagens
        message = MagicMock(spec=Message)
        message.content = "Last message"
        message.role = MessageRole.HUMAN
        
        # Configurar mocks para o banco de dados
        conversation_service.db.query.return_value.filter.return_value.first.side_effect = [
            conversation,  # Para conversa
            agent,         # Para agente
        ]
        conversation_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            message        # Última mensagem
        ]
        
        # Mock para process_message
        conversation_service.agent_service.process_message.return_value = {
            "agent_response": {"content": "Agent response"}
        }
        
        # Chamar o método
        result = await conversation_service.resume_conversation(
            conversation_id="conv-123",
            message="New message"
        )
        
        # Verificar resultado
        assert result["status"] == "resumed_with_response"
        assert result["message_processed"] == True
        assert "response" in result
        
        # Verificar se a mensagem foi processada
        conversation_service.agent_service.process_message.assert_called_once()
    
def test_detect_stuck_conversations(self, conversation_service):
    """Testa a detecção de conversas paralisadas."""
    # Mock para conversas
    conversation1 = MagicMock(spec=Conversation)
    conversation1.id = "conv-1"
    conversation2 = MagicMock(spec=Conversation)
    conversation2.id = "conv-2"
    
    # Mock para mensagens
    message1 = MagicMock(spec=Message)
    message1.role = MessageRole.HUMAN  # Última mensagem do usuário (stuck)
    
    message2 = MagicMock(spec=Message)
    message2.role = MessageRole.AGENT  # Última mensagem do agente (não stuck)
    
    # Configurar mocks
    conversation_service.db.query.return_value.filter.return_value.all.return_value = [
        conversation1, conversation2
    ]
    
    # Configurar um mock melhor para lidar com o encadeamento
    # Configurando o primeiro nível de retorno
    mock_query = MagicMock()
    conversation_service.db.query.return_value = mock_query
    
    # Configurar filtros específicos
    def get_messages_for_conversation(conv_id):
        if conv_id == "conv-1":
            return [message1]
        else:
            return [message2]
    
    # Configurando o mock para retornar o resultado correto com base no ID da conversa
    def get_filter_mock(*args, **kwargs):
        mock_filter = MagicMock()
        
        def order_by_mock(*args, **kwargs):
            mock_order = MagicMock()
            
            def first_mock():
                # Determine qual conversa está sendo pesquisada pelo filtro
                for arg in args:
                    if "conv-1" in str(arg):
                        return message1
                    elif "conv-2" in str(arg):
                        return message2
                return None
                
            mock_order.first = first_mock
            return mock_order
            
        mock_filter.order_by = order_by_mock
        return mock_filter
        
    mock_query.filter = get_filter_mock
    
    # Chamar o método
    result = conversation_service.detect_stuck_conversations(timeout_minutes=30)
    
    # Verificar resultado
    assert len(result) == 1
    assert "conv-1" in result