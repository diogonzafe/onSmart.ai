# app/tests/test_integration.py
import unittest
import asyncio
import os
import sys
from typing import Dict, Any, List
import uuid
from datetime import datetime
import json

# Adicionar diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Importar componentes para teste
from app.agents.base import BaseAgent, AgentState
from app.agents.supervisor import SupervisorAgent
from app.agents.marketing import MarketingAgent
from app.agents.sales import SalesAgent
from app.agents.finance import FinanceAgent
from app.templates.base import TemplateManager
from app.templates.marketing import get_default_marketing_templates
from app.templates.sales import get_default_sales_templates
from app.templates.finance import get_default_finance_templates
from app.models.agent import Agent, AgentType
from app.models.template import Template, TemplateDepartment
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.core.mcp import MCPFormatter, MCPResponseProcessor

# Classes de simulação para testes
class MockTemplate:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.name = kwargs.get("name", "Mock Template")
        self.description = kwargs.get("description", "Descrição do template simulado")
        self.department = kwargs.get("department", TemplateDepartment.CUSTOM)
        self.is_public = kwargs.get("is_public", True)
        self.prompt_template = kwargs.get("prompt_template", "Você é um assistente para {{especialidade}}.")
        self.tools_config = kwargs.get("tools_config", {})
        self.llm_config = kwargs.get("llm_config", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())
        self.user_id = kwargs.get("user_id", None)

class MockAgent:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.name = kwargs.get("name", "Mock Agent")
        self.description = kwargs.get("description", "Descrição do agente simulado")
        self.user_id = kwargs.get("user_id", "user123")
        self.type = kwargs.get("type", AgentType.CUSTOM)
        self.configuration = kwargs.get("configuration", {})
        self.template_id = kwargs.get("template_id", None)
        self.is_active = kwargs.get("is_active", True)
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())
        self.template = kwargs.get("template", None)

class MockConversation:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.title = kwargs.get("title", "Conversa de Teste")
        self.user_id = kwargs.get("user_id", "user123")
        self.agent_id = kwargs.get("agent_id", None)
        self.status = kwargs.get("status", ConversationStatus.ACTIVE)
        self.metadata = kwargs.get("metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())

class MockMessage:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.conversation_id = kwargs.get("conversation_id", None)
        self.role = kwargs.get("role", MessageRole.HUMAN)
        self.content = kwargs.get("content", "Mensagem de teste")
        self.metadata = kwargs.get("metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())

class MockDB:
    """Mock para simulação do banco de dados"""
    def __init__(self):
        self.data = {}
    
    def query(self, model):
        return MockQuery(self, model)
    
    def add(self, obj):
        model_name = obj.__class__.__name__.lower()
        if model_name not in self.data:
            self.data[model_name] = []
        self.data[model_name].append(obj)
    
    def commit(self):
        pass
    
    def refresh(self, obj):
        pass

class MockQuery:
    """Mock para simulação de consultas"""
    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.filters = []
    
    def filter(self, *args):
        self.filters.extend(args)
        return self
    
    def first(self):
        model_name = self.model.__name__.lower()
        items = self.db.data.get(model_name, [])
        return items[0] if items else None
    
    def all(self):
        model_name = self.model.__name__.lower()
        return self.db.data.get(model_name, [])

# Mock dos componentes MCP
class MockMCPFormatter(MCPFormatter):
    def format_conversation_context(self, db, agent, conversation, max_messages=50, include_tools=True):
        """Versão simplificada para testes"""
        return {
            "messages": [
                {"role": "system", "content": "Você é um assistente útil"},
                {"role": "user", "content": "Olá, como você está?"},
                {"role": "assistant", "content": "Estou bem, como posso ajudar?"}
            ],
            "tools": [
                {"name": "search", "description": "Pesquisa na web"},
                {"name": "calculator", "description": "Executa cálculos matemáticos"}
            ],
            "metadata": {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "conversation_id": conversation.id
            },
            "memory": {
                "facts": ["Fato 1", "Fato 2"],
                "recent_actions": []
            }
        }

class MockMCPProcessor(MCPResponseProcessor):
    def process_response(self, response: str) -> Dict[str, Any]:
        """Versão simplificada para testes"""
        return {
            "content": response,
            "filtered_content": response,
            "actions": [
                {
                    "name": "search",
                    "params": {"query": "teste"}
                }
            ],
            "validation": {
                "is_valid": True,
                "warnings": []
            }
        }

# Versão de teste do BaseAgent que não depende de LLM real
class TestBaseAgent(BaseAgent):
    async def process_message(self, conversation_id, message, metadata=None):
        """Implementação simplificada para testes"""
        # Simular processamento
        self.state.update_status("processing")
        
        # Extrair fatos da mensagem
        facts = self.extract_facts(message)
        for fact in facts:
            self.state.add_fact(fact)
        
        # Preparar uma resposta simulada
        response = f"Resposta simulada para: {message}"
        
        # Processar a resposta
        processed_response = self.mcp_processor.process_response(response)
        
        # Simular execução de ações
        action_results = await self._execute_actions(processed_response.get("actions", []))
        processed_response["action_results"] = action_results
        
        # Criar uma mensagem simulada
        message_id = str(uuid.uuid4())
        processed_response["message"] = {
            "id": message_id,
            "content": processed_response["filtered_content"],
            "role": "assistant",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Atualizar estado
        self.state.update_status("idle")
        
        return processed_response

class TestAgentTemplateIntegration(unittest.TestCase):
    """Testes de integração entre agentes e templates"""
    
    def setUp(self):
        self.db = MockDB()
        self.template_manager = TemplateManager()
        
        # Configurar mocks para MCP
        self.mcp_formatter = MockMCPFormatter()
        self.mcp_processor = MockMCPProcessor()
        
        # Carregar um template de marketing
        marketing_templates = get_default_marketing_templates()
        self.marketing_template_data = marketing_templates[0]
        
        # Criar template simulado
        self.template = MockTemplate(
            name=self.marketing_template_data["name"],
            department=self.marketing_template_data["department"],
            prompt_template=self.marketing_template_data["prompt_template"],
            tools_config=self.marketing_template_data["tools_config"],
            llm_config=self.marketing_template_data["llm_config"]
        )
        
        # Processar o template
        self.processed_template = self.template_manager.load_template(self.template)
        
        # Criar agente com o template
        self.agent_record = MockAgent(
            name="Agente de Marketing",
            type=AgentType.MARKETING,
            template=self.template,
            configuration={
                "company_name": "Empresa ABC",
                "primary_platform": "Instagram",
                "brand_tone": "casual",
                "industry": "Tecnologia",
                "target_audience": "Profissionais de TI",
                "differentials": "Inovação e qualidade",
                "metric_priority": "engajamento"
            }
        )
        
        # Criar conversa simulada
        self.conversation = MockConversation(
            agent_id=self.agent_record.id
        )
        
        # Adicionar ao "banco de dados"
        self.db.add(self.agent_record)
        self.db.add(self.conversation)
        
        # Criar agente de teste
        self.agent = TestBaseAgent(
            self.db, 
            self.agent_record,
            mcp_formatter=self.mcp_formatter,
            mcp_processor=self.mcp_processor
        )
    
    async def test_agent_template_workflow(self):
        """Testa o fluxo completo de processamento de mensagem usando template"""
        # Mensagem de teste
        test_message = "Precisamos melhorar nossa presença no Instagram. Como podemos aumentar o engajamento?"
        
        # Processar a mensagem
        response = await self.agent.process_message(
            conversation_id=self.conversation.id,
            message=test_message
        )
        
        # Verificar a resposta
        self.assertIn("message", response)
        self.assertIn("actions", response)
        
        # Verificar se o estado foi atualizado
        self.assertEqual(self.agent.state.status, "idle")
        
        # Verificar se ações foram processadas
        self.assertIn("action_results", response)
    
    def test_template_variable_extraction(self):
        """Testa a extração de variáveis do template"""
        # Verificar se o template contém as variáveis esperadas
        variables = self.processed_template["variables"]
        
        # Variáveis esperadas do template de marketing
        expected_vars = [
            "company_name", "primary_platform", "brand_tone", 
            "industry", "target_audience", "differentials", 
            "metric_priority"
        ]
        
        for var in expected_vars:
            self.assertIn(var, variables)
    
    def test_agent_template_configuration(self):
        """Testa se a configuração do agente corresponde às variáveis do template"""
        # Verificar se todas as variáveis do template estão na configuração do agente
        variables = self.processed_template["variables"]
        
        for var_name in variables:
            self.assertIn(var_name, self.agent_record.configuration)
    
    def test_template_rendering(self):
        """Testa se o template é renderizado corretamente com as configurações do agente"""
        # Renderizar o template com as configurações do agente
        rendered = self.template_manager.render_template(
            self.template.id,
            self.agent_record.configuration
        )
        
        # Verificar se a substituição foi feita corretamente
        self.assertIn("Empresa ABC", rendered)
        self.assertIn("Instagram", rendered)
        self.assertIn("casual", rendered)
        self.assertIn("Tecnologia", rendered)
        self.assertIn("Profissionais de TI", rendered)
        self.assertIn("Inovação e qualidade", rendered)
        self.assertIn("engajamento", rendered)

# Teste de integração entre diferentes tipos de agentes
class TestMultiAgentIntegration(unittest.TestCase):
    """Testes de integração entre múltiplos agentes"""
    
    def setUp(self):
        self.db = MockDB()
        
        # Configurar mocks para MCP
        self.mcp_formatter = MockMCPFormatter()
        self.mcp_processor = MockMCPProcessor()
        
        # Criar templates para os diferentes tipos de agentes
        self.supervisor_template = MockTemplate(
            name="Template Supervisor",
            department=TemplateDepartment.SUPERVISOR,
            prompt_template="Você é um agente supervisor que coordena outros agentes."
        )
        
        self.marketing_template = MockTemplate(
            name="Template Marketing",
            department=TemplateDepartment.MARKETING,
            prompt_template="Você é um especialista em marketing digital."
        )
        
        self.sales_template = MockTemplate(
            name="Template Vendas",
            department=TemplateDepartment.SALES,
            prompt_template="Você é um especialista em vendas B2B."
        )
        
        # Criar registros de agentes
        self.supervisor_record = MockAgent(
            name="Supervisor",
            type=AgentType.SUPERVISOR,
            template=self.supervisor_template
        )
        
        self.marketing_record = MockAgent(
            name="Marketing",
            type=AgentType.MARKETING,
            template=self.marketing_template,
            user_id=self.supervisor_record.user_id
        )
        
        self.sales_record = MockAgent(
            name="Vendas",
            type=AgentType.SALES,
            template=self.sales_template,
            user_id=self.supervisor_record.user_id
        )
        
        # Adicionar ao "banco de dados"
        self.db.add(self.supervisor_record)
        self.db.add(self.marketing_record)
        self.db.add(self.sales_record)
        
        # Criar conversa
        self.conversation = MockConversation(
            agent_id=self.supervisor_record.id
        )
        self.db.add(self.conversation)
        
        # Criar instâncias dos agentes
        self.supervisor = SupervisorAgent(
            self.db, 
            self.supervisor_record,
            mcp_formatter=self.mcp_formatter,
            mcp_processor=self.mcp_processor
        )
        
        self.marketing_agent = TestBaseAgent(
            self.db, 
            self.marketing_record,
            mcp_formatter=self.mcp_formatter,
            mcp_processor=self.mcp_processor
        )
        
        self.sales_agent = TestBaseAgent(
            self.db, 
            self.sales_record,
            mcp_formatter=self.mcp_formatter,
            mcp_processor=self.mcp_processor
        )
    
    async def test_supervisor_delegation(self):
        """Testa a capacidade do supervisor de delegar tarefas aos agentes corretos"""
        # 1. Mensagem relacionada a marketing
        marketing_message = "Precisamos uma estratégia para as redes sociais da empresa"
        
        # O supervisor deve identificar que esta é uma tarefa de marketing
        response = await self.supervisor.process_message(
            conversation_id=self.conversation.id,
            message=marketing_message
        )
        
        # Verificar se o supervisor identificou o departamento correto
        dept = self.supervisor._determine_department(marketing_message, {})
        self.assertEqual(dept, "marketing")
        
        # 2. Mensagem relacionada a vendas
        sales_message = "Como podemos aumentar as vendas e melhorar a conversão de leads?"
        
        # O supervisor deve identificar que esta é uma tarefa de vendas
        response = await self.supervisor.process_message(
            conversation_id=self.conversation.id,
            message=sales_message
        )
        
        # Verificar se o supervisor identificou o departamento correto
        dept = self.supervisor._determine_department(sales_message, {})
        self.assertEqual(dept, "sales")
    
    async def test_departmental_agent_responses(self):
        """Testa se os agentes departamentais respondem de acordo com sua especialidade"""
        # Mensagem de marketing
        marketing_message = "Como podemos melhorar nossa presença nas redes sociais?"
        
        # Processar com o agente de marketing
        marketing_response = await self.marketing_agent.process_message(
            conversation_id=self.conversation.id,
            message=marketing_message
        )
        
        # Mensagem de vendas
        sales_message = "Como podemos fechar mais negócios este mês?"
        
        # Processar com o agente de vendas
        sales_response = await self.sales_agent.process_message(
            conversation_id=self.conversation.id,
            message=sales_message
        )
        
        # Verificar se ambos geraram respostas
        self.assertIn("message", marketing_response)
        self.assertIn("message", sales_response)
        
        # Nas implementações reais, verificaríamos a especialização das respostas

# Executar os testes
if __name__ == "__main__":
    unittest.main()