# tests/test_tenant.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch

from app.middleware.tenant import TenantMiddleware
from app.core.tenant import tenant_filter
from app.models.organization import Organization
from app.models.agent import Agent
from app.main import app
from app.db.database import get_db

# Configurar o cliente de teste
app.add_middleware(TenantMiddleware)
client = TestClient(app)

def override_get_db():
    """Sobrescreve a função get_db para usar um mock."""
    return MagicMock(spec=Session)

app.dependency_overrides[get_db] = override_get_db

class TestTenantMiddleware:
    def test_tenant_header_extraction(self):
        """Testa se o middleware extrai corretamente o tenant do header."""
        # Mock para o middleware
        request = MagicMock()
        request.headers = {"X-Tenant-ID": "test-tenant-123"}
        
        middleware = TenantMiddleware(app)
        
        # Mock para call_next
        async def mock_call_next(request):
            # Aqui verificamos se o tenant_id foi definido corretamente
            assert hasattr(request.state, "tenant_id")
            assert request.state.tenant_id == "test-tenant-123"
            return MagicMock()
        
        # Executar o middleware
        import asyncio
        asyncio.run(middleware.dispatch(request, mock_call_next))

class TestTenantFilter:
    def test_tenant_filter_applies_correctly(self):
        """Testa se o filtro de tenant é aplicado corretamente às queries."""
        # Mock para Query, Model e Request
        query = MagicMock()
        model = MagicMock()
        model.__name__ = "TestModel"
        
        # Configurar model para ter organization_id
        model.organization_id = "org_column"
        
        request = MagicMock()
        request.state.tenant_id = "tenant-456"
        
        # Aplicar filtro
        tenant_filter(query, model, request)
        
        # Verificar se o filtro foi aplicado
        query.filter.assert_called_once()

class TestOrganizationModel:
    def test_organization_relationships(self):
        """Testa as relações do modelo Organization."""
        # Criar organização com relações
        org = Organization(
            id="org-123",
            name="Test Org",
            slug="test-org"
        )
        
        # Verificar se os relacionamentos estão definidos
        assert hasattr(org, "users")
        assert hasattr(org, "agents")
        assert hasattr(org, "templates")
        assert hasattr(org, "tools")