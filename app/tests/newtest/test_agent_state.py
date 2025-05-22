# app/tests/newtest/test_agent_state.py - Versão corrigida final
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
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
        
        # CORREÇÃO: Mock para process_message deve ser uma coroutine
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

# CORREÇÃO: Versão simplificada que funciona
@pytest.mark.asyncio 
async def test_detect_stuck_conversations():
    """Testa a detecção de conversas paralisadas."""
    # Criar serviço mock
    db = MagicMock()
    conversation_service = ConversationService(db)
    
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
    
    # SOLUÇÃO SIMPLIFICADA: Usar patch diretamente para cada query
    with patch.object(conversation_service.db, 'query') as mock_query:
        # Configurar retorno para query de conversas
        conversations_result = MagicMock()
        conversations_result.filter.return_value.all.return_value = [conversation1, conversation2]
        
        # Configurar retornos para queries de mensagens
        message1_result = MagicMock()
        message1_result.filter.return_value.order_by.return_value.first.return_value = message1
        
        message2_result = MagicMock()
        message2_result.filter.return_value.order_by.return_value.first.return_value = message2
        
        # Configurar side_effect para distinguir os tipos de query
        def query_side_effect(model):
            if model == Conversation:
                return conversations_result
            elif model == Message:
                # Retornar diferentes resultados baseado em chamadas sequenciais
                if not hasattr(query_side_effect, 'message_call_count'):
                    query_side_effect.message_call_count = 0
                
                if query_side_effect.message_call_count == 0:
                    query_side_effect.message_call_count += 1
                    return message1_result  # Primeira conversa -> stuck
                else:
                    return message2_result  # Segunda conversa -> não stuck
            
            return MagicMock()
        
        mock_query.side_effect = query_side_effect
        
        # Chamar o método
        result = conversation_service.detect_stuck_conversations(timeout_minutes=30)
        
        # Verificar resultado - apenas conv-1 deve estar stuck
        assert len(result) == 1
        assert "conv-1" in result