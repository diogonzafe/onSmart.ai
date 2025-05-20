# app/tests/test_agents.py
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
from app.models.agent import Agent, AgentType
from app.models.template import Template, TemplateDepartment

# Definir classes de teste simuladas
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

class TestAgentState(unittest.TestCase):
    """Testes para a classe AgentState"""
    
    def setUp(self):
        self.state = AgentState()
    
    def test_init(self):
        """Testa a inicialização do estado"""
        self.assertEqual(self.state.status, "idle")
        self.assertIsNone(self.state.error)
        self.assertIn("facts", self.state.memory)
        self.assertIn("recent_actions", self.state.memory)
        self.assertIn("priorities", self.state.memory)
    
    def test_update_status(self):
        """Testa a atualização de status"""
        self.state.update_status("processing", "Teste de erro")
        self.assertEqual(self.state.status, "processing")
        self.assertEqual(self.state.error, "Teste de erro")
    
    def test_add_fact(self):
        """Testa adição de fatos"""
        self.state.add_fact("Fato de teste 1")
        self.state.add_fact("Fato de teste 2")
        self.assertEqual(len(self.state.memory["facts"]), 2)
        self.assertIn("Fato de teste 1", self.state.memory["facts"])
        
        # Testar limite de fatos
        for i in range(25):
            self.state.add_fact(f"Fato {i}")
        self.assertEqual(len(self.state.memory["facts"]), 20)
    
    def test_add_action(self):
        """Testa registro de ações"""
        self.state.add_action({"name": "test_action", "params": {"test": True}})
        self.assertEqual(len(self.state.memory["recent_actions"]), 1)
        self.assertEqual(self.state.memory["recent_actions"][0]["action"]["name"], "test_action")
    
    def test_set_priority(self):
        """Testa definição de prioridades"""
        self.state.set_priority("accuracy", 9)
        self.state.set_priority("speed", 7)
        
        # Verificar se as prioridades foram definidas
        priorities = {p["name"]: p["value"] for p in self.state.memory["priorities"]}
        self.assertEqual(priorities["accuracy"], 9)
        self.assertEqual(priorities["speed"], 7)
        
        # Atualizar uma prioridade existente
        self.state.set_priority("accuracy", 8)
        priorities = {p["name"]: p["value"] for p in self.state.memory["priorities"]}
        self.assertEqual(priorities["accuracy"], 8)

class TestBaseAgent(unittest.TestCase):
    """Testes para a classe base de agentes"""
    
    def setUp(self):
        self.db = MockDB()
        
        # Criar template simulado
        self.template = MockTemplate(
            prompt_template="Você é um assistente especializado em {{especialidade}}.",
            tools_config={"allowed_tools": ["search", "calculator"]},
            llm_config={"model": "test_model", "temperature": 0.7}
        )
        
        # Criar agente simulado
        self.agent_record = MockAgent(
            name="Agente de Teste",
            type=AgentType.CUSTOM,
            configuration={"especialidade": "testes automatizados"},
            template=self.template
        )
        
        # Classe concreta para testes
        class TestableAgent(BaseAgent):
            async def process_message(self, conversation_id, message, metadata=None):
                # Implementação mínima para teste
                return {
                    "content": f"Resposta simulada para: {message}",
                    "actions": []
                }
        
        self.agent = TestableAgent(self.db, self.agent_record)
    
    def test_init(self):
        """Testa a inicialização do agente"""
        self.assertEqual(self.agent.name, "Agente de Teste")
        self.assertEqual(self.agent.agent_type, AgentType.CUSTOM)
        self.assertEqual(self.agent.configuration["especialidade"], "testes automatizados")
        self.assertEqual(self.agent.prompt_template, "Você é um assistente especializado em {{especialidade}}.")
        self.assertEqual(self.agent.tools_config, {"allowed_tools": ["search", "calculator"]})
        self.assertEqual(self.agent.llm_config, {"model": "test_model", "temperature": 0.7})
    
    def test_extract_facts(self):
        """Testa a extração de fatos"""
        text = """
        A Terra é o terceiro planeta do Sistema Solar.
        Ela possui uma atmosfera composta principalmente de nitrogênio e oxigênio.
        A água no estado líquido é abundante na superfície terrestre.
        O tempo está bom hoje.
        """
        
        facts = self.agent.extract_facts(text)
        self.assertGreater(len(facts), 0)
        
        # Verificar se encontrou pelo menos um dos fatos importantes
        important_facts = [
            "A Terra é o terceiro planeta do Sistema Solar",
            "Ela possui uma atmosfera composta principalmente de nitrogênio e oxigênio",
            "A água no estado líquido é abundante na superfície terrestre"
        ]
        
        found = False
        for fact in facts:
            if any(important in fact for important in important_facts):
                found = True
                break
        
        self.assertTrue(found, "Não identificou nenhum fato relevante")

# Testes para os agentes específicos
class TestSupervisorAgent(unittest.TestCase):
    """Testes para o agente supervisor"""
    
    def setUp(self):
        self.db = MockDB()
        
        # Criar template simulado
        self.template = MockTemplate(
            department=TemplateDepartment.SUPERVISOR,
            prompt_template="Você é um agente supervisor responsável por coordenar outros agentes."
        )
        
        # Criar agente supervisor
        self.agent_record = MockAgent(
            name="Supervisor",
            type=AgentType.SUPERVISOR,
            template=self.template
        )
        
        # Criar agentes subordinados
        marketing_agent = MockAgent(
            name="Marketing",
            type=AgentType.MARKETING,
            user_id=self.agent_record.user_id
        )
        
        sales_agent = MockAgent(
            name="Vendas",
            type=AgentType.SALES,
            user_id=self.agent_record.user_id
        )
        
        finance_agent = MockAgent(
            name="Finanças",
            type=AgentType.FINANCE,
            user_id=self.agent_record.user_id
        )
        
        # Adicionar agentes ao "banco de dados"
        self.db.add(self.agent_record)
        self.db.add(marketing_agent)
        self.db.add(sales_agent)
        self.db.add(finance_agent)
        
        # Criar o agente
        self.agent = SupervisorAgent(self.db, self.agent_record)
    
    def test_init(self):
        """Testa a inicialização do agente supervisor"""
        self.assertEqual(self.agent.name, "Supervisor")
        self.assertEqual(self.agent.agent_type, AgentType.SUPERVISOR)
        
        # Verificar se identificou os agentes subordinados
        self.assertIn("marketing", self.agent.department_agents)
        self.assertIn("sales", self.agent.department_agents)
        self.assertIn("finance", self.agent.department_agents)
    
    def test_determine_department(self):
        """Testa a determinação de departamento com base na mensagem"""
        # Teste para mensagem de marketing
        marketing_message = "Precisamos melhorar nossa campanha de publicidade nas redes sociais"
        dept = self.agent._determine_department(marketing_message, {})
        self.assertEqual(dept, "marketing")
        
        # Teste para mensagem de vendas
        sales_message = "Qual é o desconto que podemos oferecer para este cliente? Precisamos fechar esta venda."
        dept = self.agent._determine_department(sales_message, {})
        self.assertEqual(dept, "sales")
        
        # Teste para mensagem de finanças
        finance_message = "Precisamos analisar o orçamento deste mês e verificar as despesas da contabilidade."
        dept = self.agent._determine_department(finance_message, {})
        self.assertEqual(dept, "finance")
        
        # Teste para mensagem genérica
        generic_message = "Olá, como você está hoje?"
        dept = self.agent._determine_department(generic_message, {})
        self.assertEqual(dept, "custom")

class TestDepartmentAgents(unittest.TestCase):
    """Testes para os agentes departamentais"""
    
    def setUp(self):
        self.db = MockDB()
        
        # Templates
        self.marketing_template = MockTemplate(
            department=TemplateDepartment.MARKETING,
            prompt_template="Você é um especialista em marketing e comunicação."
        )
        
        self.sales_template = MockTemplate(
            department=TemplateDepartment.SALES,
            prompt_template="Você é um especialista em vendas e negociação."
        )
        
        self.finance_template = MockTemplate(
            department=TemplateDepartment.FINANCE,
            prompt_template="Você é um especialista em finanças e análise financeira."
        )
        
        # Agentes
        self.marketing_agent_record = MockAgent(
            name="Marketing",
            type=AgentType.MARKETING,
            template=self.marketing_template,
            configuration={"expertise": "redes sociais", "channels": ["instagram", "facebook"]}
        )
        
        self.sales_agent_record = MockAgent(
            name="Vendas",
            type=AgentType.SALES,
            template=self.sales_template,
            configuration={"sales_type": "b2b", "products": ["produto A", "produto B"]}
        )
        
        self.finance_agent_record = MockAgent(
            name="Finanças",
            type=AgentType.FINANCE,
            template=self.finance_template,
            configuration={"finance_areas": ["budgeting", "analysis"], "currency": "BRL"}
        )
        
        # Instanciar agentes
        self.marketing_agent = MarketingAgent(self.db, self.marketing_agent_record)
        self.sales_agent = SalesAgent(self.db, self.sales_agent_record)
        self.finance_agent = FinanceAgent(self.db, self.finance_agent_record)
    
    def test_marketing_agent_init(self):
        """Testa a inicialização do agente de marketing"""
        self.assertEqual(self.marketing_agent.name, "Marketing")
        self.assertEqual(self.marketing_agent.expertise, "redes sociais")
        self.assertEqual(self.marketing_agent.channels, ["instagram", "facebook"])
        
        # Verificar prioridades
        priorities = {p["name"]: p["value"] for p in self.marketing_agent.state.memory["priorities"]}
        self.assertIn("creativity", priorities)
        self.assertIn("audience_understanding", priorities)
    
    def test_sales_agent_init(self):
        """Testa a inicialização do agente de vendas"""
        self.assertEqual(self.sales_agent.name, "Vendas")
        self.assertEqual(self.sales_agent.sales_type, "b2b")
        self.assertEqual(self.sales_agent.products, ["produto A", "produto B"])
        
        # Verificar prioridades
        priorities = {p["name"]: p["value"] for p in self.sales_agent.state.memory["priorities"]}
        self.assertIn("customer_satisfaction", priorities)
        self.assertIn("closing_ability", priorities)
    
    def test_finance_agent_init(self):
        """Testa a inicialização do agente financeiro"""
        self.assertEqual(self.finance_agent.name, "Finanças")
        self.assertEqual(self.finance_agent.finance_areas, ["budgeting", "analysis"])
        self.assertEqual(self.finance_agent.currency, "BRL")
        
        # Verificar prioridades
        priorities = {p["name"]: p["value"] for p in self.finance_agent.state.memory["priorities"]}
        self.assertIn("accuracy", priorities)
        self.assertIn("compliance", priorities)

# Executar os testes
if __name__ == "__main__":
    unittest.main()