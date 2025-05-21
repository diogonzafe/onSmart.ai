# tests/test_batch_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.core.security import get_current_active_user
import json

from app.main import app
# Update the import path below if batch_api is located elsewhere in your project structure
# For example, if batch_api.py is in app/batch_api.py, use:
# from app.batch_api import router as batch_router

from app.api.batch_api import router as batch_router


# Adicionar router ao app para testes
app.include_router(batch_router)
client = TestClient(app)

# Mock para get_current_active_user
async def mock_get_current_user():
    user = MagicMock()
    user.id = "user-123"
    return user

app.dependency_overrides[get_current_active_user] = mock_get_current_user

class TestBatchOperations:
    @pytest.fixture
    def agent_service_mock(self):
        """Fixture para mock do serviço de agentes."""
        with patch('app.api.batch_api.get_agent_service') as mock:
            agent_service = MagicMock()
            mock.return_value = agent_service
            yield agent_service
    
    @pytest.fixture
    def template_service_mock(self):
        """Fixture para mock do serviço de templates."""
        with patch('app.api.batch_api.get_template_service') as mock:
            template_service = MagicMock()
            mock.return_value = template_service
            yield template_service
    
    def test_batch_update_agents(self, agent_service_mock):
        """Testa atualização em lote de agentes."""
        # Configurar mock para get_agent
        agent1 = MagicMock()
        agent1.id = "agent-1"
        agent1.user_id = "user-123"
        
        agent2 = MagicMock()
        agent2.id = "agent-2"
        agent2.user_id = "user-123"
        
        # Retornar agentes diferentes com base no ID
        def mock_get_agent(agent_id):
            if agent_id == "agent-1":
                return agent1
            else:
                return agent2
        
        agent_service_mock.get_agent.side_effect = mock_get_agent
        
        # Configurar mock para update_agent
        def mock_update_agent(agent_id, **kwargs):
            agent = MagicMock()
            agent.id = agent_id
            return agent
        
        agent_service_mock.update_agent.side_effect = mock_update_agent
        
        # Dados para o teste
        data = [
            {
                "agent_id": "agent-1",
                "name": "Updated Agent 1",
                "description": "New description 1",
                "is_active": True
            },
            {
                "agent_id": "agent-2",
                "name": "Updated Agent 2",
                "description": "New description 2",
                "is_active": False
            }
        ]
        
        # Fazer a requisição
        response = client.post("/api/batch/agents/update", json=data)
        
        # Verificar resposta
        assert response.status_code == 200
        
        # Verificar resultado
        result = response.json()
        assert "results" in result
        assert len(result["results"]) == 2
        
        # Verificar se update_agent foi chamado para cada agente
        assert agent_service_mock.update_agent.call_count == 2
    
    def test_batch_create_agents(self, agent_service_mock):
        """Testa criação em lote de agentes."""
        # Configurar mock para create_agent
        def mock_create_agent(user_id, **kwargs):
            agent = MagicMock()
            agent.id = f"new-agent-{kwargs['name']}"
            return agent
        
        agent_service_mock.create_agent.side_effect = mock_create_agent
        
        # Dados para o teste
        data = [
            {
                "name": "New Agent 1",
                "description": "Description 1",
                "agent_type": "MARKETING",
                "template_id": "template-1",
                "configuration": {"key": "value"}
            },
            {
                "name": "New Agent 2",
                "description": "Description 2",
                "agent_type": "SALES",
                "template_id": "template-2",
                "configuration": {"key": "value"}
            }
        ]
        
        # Fazer a requisição
        response = client.post("/api/batch/agents/create", json=data)
        
        # Verificar resposta
        assert response.status_code == 200
        
        # Verificar resultado
        result = response.json()
        assert "results" in result
        assert len(result["results"]) == 2
        
        # Verificar se create_agent foi chamado para cada agente
        assert agent_service_mock.create_agent.call_count == 2
        
        # Verificar se o user_id foi passado corretamente
        for call in agent_service_mock.create_agent.call_args_list:
            assert call[1]["user_id"] == "user-123"

# tests/test_patch_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.models.agent import Agent
from app.models.template import Template

client = TestClient(app)

class TestPatchOperations:
    @pytest.fixture
    def db_mock(self):
        """Fixture para mock do banco de dados."""
        with patch('app.api.agents_api.get_db') as mock:
            db = MagicMock()
            mock.return_value.__next__.return_value = db
            yield db
    
    @pytest.fixture
    def current_user_mock(self):
        """Fixture para mock do usuário autenticado."""
        with patch('app.api.agents_api.get_current_active_user') as mock:
            user = MagicMock()
            user.id = "user-123"
            mock.return_value = user
            yield user
    
    @pytest.fixture
    def agent_service_mock(self):
        """Fixture para mock do serviço de agentes."""
        with patch('app.api.agents_api.get_agent_service') as mock:
            service = MagicMock()
            mock.return_value = service
            yield service
    
    def test_patch_agent(self, db_mock, current_user_mock, agent_service_mock):
        """Testa atualização parcial de agente."""
        # Mock para query de agente
        agent = MagicMock(spec=Agent)
        agent.id = "agent-123"
        agent.user_id = "user-123"
        db_mock.query.return_value.filter.return_value.first.return_value = agent
        
        # Mock para update_agent
        updated_agent = MagicMock(spec=Agent)
        updated_agent.id = "agent-123"
        updated_agent.name = "Updated Name"
        agent_service_mock.update_agent.return_value = updated_agent
        
        # Dados para o patch
        data = {
            "name": "Updated Name",
            "is_active": True
        }
        
        # Fazer a requisição
        response = client.patch("/api/agents/agent-123", json=data)
        
        # Verificar resposta
        assert response.status_code == 200
        
        # Verificar se update_agent foi chamado com os parâmetros corretos
        agent_service_mock.update_agent.assert_called_once_with(
            agent_id="agent-123",
            name="Updated Name",
            description=None,
            is_active=True,
            configuration=None
        )

# tests/test_preview_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import json

from app.main import app
from app.api.test_api import router as test_router

# Adicionar router ao app para testes
app.include_router(test_router)
client = TestClient(app)

class TestPreviewOperations:
    @pytest.fixture
    def template_service_mock(self):
        """Fixture para mock do serviço de templates."""
        with patch('app.api.test_api.get_template_service') as mock:
            service = MagicMock()
            mock.return_value = service
            yield service
    
    @pytest.fixture
    def agent_service_mock(self):
        """Fixture para mock do serviço de agentes."""
        with patch('app.api.test_api.get_agent_service') as mock:
            service = MagicMock()
            mock.return_value = service
            yield service
    
    def test_template_render(self, template_service_mock):
        """Testa preview de renderização de template."""
        # Mock para preview_template
        template_service_mock.preview_template.return_value = "Hello, John! Welcome to Acme Inc."
        
        # Dados para o teste
        data = {
            "template_data": {
                "prompt_template": "Hello, {{name}}! Welcome to {{company}}."
            },
            "variables": {
                "name": "John",
                "company": "Acme Inc"
            }
        }
        
        # Fazer a requisição
        response = client.post("/api/test/template/render", json=data)
        
        # Verificar resposta
        assert response.status_code == 200
        
        # Verificar resultado
        result = response.json()
        assert "preview" in result
        assert result["preview"] == "Hello, John! Welcome to Acme Inc."
        
        # Verificar se o método correto foi chamado
        template_service_mock.preview_template.assert_called_once()
        
    def test_agent_test(self, agent_service_mock):
        """Testa simulação de agente sem criar conversa permanente."""
        # Mock para create_agent
        temp_agent = MagicMock()
        temp_agent.id = "temp-agent-id"
        agent_service_mock.create_agent.return_value = temp_agent
        
        # Mock para process_message
        response_data = {
            "agent_response": {
                "message": {
                    "content": "Test response from agent"
                }
            }
        }
        agent_service_mock.process_message.return_value = response_data
        
        # Dados para o teste
        data = {
            "agent_data": {
                "agent_type": "MARKETING",
                "template_id": "template-123",
                "configuration": {"key": "value"}
            },
            "message": "Test message for agent"
        }
        
        # Fazer a requisição
        response = client.post("/api/test/agent", json=data)
        
        # Verificar resposta
        assert response.status_code == 200
        
        # Verificar resultado
        result = response.json()
        assert "response" in result
        assert result["temp"] == True
        assert result["agent_type"] == "MARKETING"
        assert result["message"] == "Test message for agent"
        
        # Verificar se os métodos corretos foram chamados
        agent_service_mock.create_agent.assert_called_once()
        agent_service_mock.process_message.assert_called_once()
        agent_service_mock.delete_agent.assert_called_once_with(temp_agent.id)