# app/tests/conftest.py - Versão melhorada com melhor isolamento
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import os

from app.main import app
from app.models.user import User
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.message import Message
from app.core.security import get_current_active_user
from app.db.database import get_db

# Configurar variáveis de ambiente para testes
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DB_NAME"] = "test_onsmart"

# Configuração pytest-asyncio
pytest_plugins = ['pytest_asyncio']

@pytest.fixture(scope="session")
def event_loop():
    """Cria um event loop para toda a sessão de testes."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Mocks globais para dependências
def create_mock_user():
    """Cria um mock de usuário consistente."""
    user = MagicMock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.name = "Test User"
    user.is_active = True
    user.is_verified = True
    return user

def create_mock_db():
    """Cria um mock de sessão do banco."""
    return MagicMock(spec=Session)

# Fixtures principais
@pytest.fixture
def mock_db():
    """Mock para sessão do banco de dados."""
    return create_mock_db()

@pytest.fixture
def mock_user():
    """Mock para usuário."""
    return create_mock_user()

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
def authenticated_client():
    """Cliente de teste FastAPI com autenticação configurada."""
    # Configurar mocks de dependência
    app.dependency_overrides[get_current_active_user] = create_mock_user
    app.dependency_overrides[get_db] = create_mock_db
    
    client = TestClient(app)
    
    yield client
    
    # Limpeza após teste
    app.dependency_overrides.clear()

@pytest.fixture
def test_client():
    """Cliente de teste FastAPI básico."""
    return TestClient(app)

@pytest.fixture
def cache():
    """Mock para cache."""
    cache_mock = MagicMock()
    cache_mock.get = MagicMock(return_value=None)
    cache_mock.set = MagicMock(return_value=True)
    cache_mock.delete = MagicMock(return_value=True)
    cache_mock.flush = MagicMock(return_value=True)
    return cache_mock

# Configuração para isolamento entre testes
@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset do estado do app entre testes."""
    # Limpar dependency overrides anteriores
    original_overrides = app.dependency_overrides.copy()
    
    yield
    
    # Restaurar estado original
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)

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
        mock.create_draft_from_template = MagicMock()
        mock.publish_draft = MagicMock()
        return mock
    return create_mock

# Fixtures para testes de autenticação
@pytest.fixture
def mock_auth_dependencies():
    """Configura mocks para autenticação."""
    def setup_auth():
        app.dependency_overrides[get_current_active_user] = create_mock_user
        app.dependency_overrides[get_db] = create_mock_db
    
    def teardown_auth():
        if get_current_active_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_active_user]
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]
    
    setup_auth()
    yield
    teardown_auth()

# Fixture para configuração de testes assíncronos
@pytest.fixture
def async_mock():
    """Cria mocks assíncronos quando necessário."""
    def create_async_mock(*args, **kwargs):
        async def async_func(*a, **kw):
            return MagicMock(*args, **kwargs)
        return async_func
    return create_async_mock