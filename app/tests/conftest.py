# app/tests/conftest.py - Versão melhorada
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.message import Message

# Configuração pytest-asyncio melhorada
pytest_plugins = ['pytest_asyncio']

@pytest.fixture(scope="session")
def event_loop():
    """Cria um event loop para toda a sessão de testes."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_db():
    """Mock para sessão do banco de dados."""
    return MagicMock(spec=Session)

@pytest.fixture
def mock_user():
    """Mock para usuário."""
    user = MagicMock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.name = "Test User"
    user.is_active = True
    return user

@pytest.fixture
def mock_agent():
    """Mock para agente."""
    agent = MagicMock(spec=Agent)
    agent.id = "test-agent-123"
    agent.name = "Test Agent"
    agent.user_id = "test-user-123"
    agent.is_active = True
    return agent

@pytest.fixture
def mock_conversation():
    """Mock para conversa."""
    conversation = MagicMock(spec=Conversation)
    conversation.id = "test-conv-123"
    conversation.title = "Test Conversation"
    conversation.user_id = "test-user-123"
    conversation.agent_id = "test-agent-123"
    return conversation

@pytest.fixture
def test_client():
    """Cliente de teste FastAPI."""
    return TestClient(app)

@pytest.fixture
def cache():
    """Mock para cache."""
    cache_mock = MagicMock()
    cache_mock.get = MagicMock(return_value=None)
    cache_mock.set = MagicMock(return_value=True)
    cache_mock.delete = MagicMock(return_value=True)
    return cache_mock

# Configuração para melhor isolamento dos testes
@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset do estado do app entre testes."""
    # Limpar dependency overrides anteriores
    app.dependency_overrides.clear()
    yield
    # Limpar novamente após o teste
    app.dependency_overrides.clear()

# Mock factories
@pytest.fixture
def agent_service_factory():
    """Factory para criar mocks do AgentService."""
    def create_mock():
        mock = MagicMock()
        mock.create_agent = MagicMock()
        mock.update_agent = MagicMock()
        mock.get_agent = MagicMock()
        mock.list_agents = MagicMock()
        mock.delete_agent = MagicMock()
        mock.process_message = MagicMock()
        return mock
    return create_mock

@pytest.fixture
def template_service_factory():
    """Factory para criar mocks do TemplateService."""
    def create_mock():
        mock = MagicMock()
        mock.create_template = MagicMock()
        mock.update_template = MagicMock()
        mock.get_template = MagicMock()
        mock.list_templates = MagicMock()
        mock.delete_template = MagicMock()
        mock.preview_template = MagicMock()
        return mock
    return create_mock