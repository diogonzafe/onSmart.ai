# app/tests/newtest/test_agent_state.py - Versão corrigida
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

from app.agents.base import AgentState

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
        # CORREÇÃO: Mock completo do banco de dados
        db = MagicMock()
        
        # CORREÇÃO: Usar patch para evitar problemas de importação circular
        with patch('app.services.conversation_service.get_agent_service') as mock_agent_service_factory:
            agent_service = MagicMock()
            mock_agent_service_factory.return_value = agent_service
            
            # Importar aqui para evitar problemas de inicialização do SQLAlchemy
            from app.services.conversation_service import ConversationService
            service = ConversationService(db)
            service.agent_service = agent_service
            
            return service
    
    @pytest.mark.asyncio
    async def test_resume_conversation(self, conversation_service):
        """Testa a retomada de uma conversa."""
        # CORREÇÃO: Mock mais simples sem dependência de modelos SQLAlchemy
        conversation = MagicMock()
        conversation.id = "conv-123"
        conversation.agent_id = "agent-123"
        conversation.status = "active"  # Usar string em vez de enum
        
        agent = MagicMock()
        agent.id = "agent-123"
        
        message = MagicMock()
        message.content = "Last message"
        message.role = "human"  # Usar string em vez de enum
        
        # CORREÇÃO: Configurar mocks de forma mais robusta
        def mock_query_side_effect(model):
            query_mock = MagicMock()
            if hasattr(model, '__name__') and model.__name__ == 'Conversation':
                query_mock.filter.return_value.first.return_value = conversation
            elif hasattr(model, '__name__') and model.__name__ == 'Agent':
                query_mock.filter.return_value.first.return_value = agent
            elif hasattr(model, '__name__') and model.__name__ == 'Message':
                query_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [message]
            else:
                # Para qualquer outro modelo, retornar mock genérico
                query_mock.filter.return_value.first.return_value = None
            return query_mock
        
        conversation_service.db.query.side_effect = mock_query_side_effect
        
        # Mock para process_message deve ser uma coroutine
        async def mock_process_message(*args, **kwargs):
            return {
                "agent_response": {"content": "Agent response"}
            }
        
        conversation_service.agent_service.process_message = mock_process_message
        
        # Chamar o método
        result = await conversation_service.resume_conversation(
            conversation_id="conv-123",
            message="New message"
        )
        
        # Verificar resultado
        assert result["status"] == "resumed_with_response"
        assert result["message_processed"] == True
        assert "response" in result

@pytest.mark.asyncio 
async def test_detect_stuck_conversations():
    """Testa a detecção de conversas paralisadas."""
    # CORREÇÃO: Mock mais simples do serviço
    db = MagicMock()
    
    # Mock das dependências para evitar problemas de importação
    with patch('app.services.conversation_service.get_agent_service') as mock_agent_service:
        mock_agent_service.return_value = MagicMock()
        
        from app.services.conversation_service import ConversationService
        conversation_service = ConversationService(db)
        
        # Mock para conversas
        conversation1 = MagicMock()
        conversation1.id = "conv-1"
        conversation2 = MagicMock()
        conversation2.id = "conv-2"
        
        # Mock para mensagens
        message1 = MagicMock()
        message1.role = "human"  # Última mensagem do usuário (stuck)
        
        message2 = MagicMock()
        message2.role = "agent"  # Última mensagem do agente (não stuck)
        
        # CORREÇÃO: Configurar mocks de forma mais robusta
        call_count = 0
        def mock_query_side_effect(model):
            nonlocal call_count
            query_mock = MagicMock()
            
            # Primeira chamada: buscar conversas
            if call_count == 0:
                query_mock.filter.return_value.all.return_value = [conversation1, conversation2]
                call_count += 1
            # Segunda chamada: primeira conversa
            elif call_count == 1:
                query_mock.filter.return_value.order_by.return_value.first.return_value = message1
                call_count += 1
            # Terceira chamada: segunda conversa
            else:
                query_mock.filter.return_value.order_by.return_value.first.return_value = message2
            
            return query_mock
        
        conversation_service.db.query.side_effect = mock_query_side_effect
        
        # Chamar o método
        result = conversation_service.detect_stuck_conversations(timeout_minutes=30)
        
        # Verificar resultado - apenas conv-1 deve estar stuck
        assert len(result) == 1
        assert "conv-1" in result