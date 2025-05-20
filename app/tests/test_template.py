# app/tests/test_templates.py
import unittest
import asyncio
import os
import sys
from typing import Dict, Any, List
import uuid
from datetime import datetime

# Adicionar diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Importar componentes para teste
from app.templates.base import TemplateManager
from app.templates.marketing import get_default_marketing_templates
from app.templates.sales import get_default_sales_templates
from app.templates.finance import get_default_finance_templates
from app.models.template import TemplateDepartment

# Classe de mock para Template
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

class TestTemplateManager(unittest.TestCase):
    """Testes para o gerenciador de templates"""
    
    def setUp(self):
        self.manager = TemplateManager()
        
        # Criar template de teste
        self.test_template = MockTemplate(
            name="Template de Teste",
            prompt_template="""
            Você é um assistente especializado em {{especialidade}}.
            
            Seu objetivo é ajudar com tarefas relacionadas a {{objetivo}} seguindo
            o estilo de comunicação {{estilo:choice=formal,casual,técnico}} com o
            cliente {{nome_cliente}}.
            
            Se precisar enviar um email, use {{email_cliente:email}}.
            
            O orçamento disponível é {{valor_orcamento:number=1000}}.
            
            A data de entrega é {{data_entrega:date=2023-12-31}}.
            """
        )
    
    def test_load_template(self):
        """Testa o carregamento de um template"""
        processed = self.manager.load_template(self.test_template)
        
        # Verificar se processou corretamente
        self.assertEqual(processed["id"], self.test_template.id)
        self.assertEqual(processed["name"], "Template de Teste")
        
        # Verificar se extraiu as variáveis
        self.assertIn("especialidade", processed["variables"])
        self.assertIn("objetivo", processed["variables"])
        self.assertIn("estilo", processed["variables"])
        self.assertIn("email_cliente", processed["variables"])
        self.assertIn("valor_orcamento", processed["variables"])
        self.assertIn("data_entrega", processed["variables"])
        
        # Verificar tipos e padrões
        self.assertEqual(processed["variables"]["estilo"]["type"], "choice")
        self.assertEqual(processed["variables"]["email_cliente"]["type"], "email")
        self.assertEqual(processed["variables"]["valor_orcamento"]["type"], "number")
        self.assertEqual(processed["variables"]["valor_orcamento"]["default"], "1000")
        self.assertEqual(processed["variables"]["data_entrega"]["type"], "date")
        self.assertEqual(processed["variables"]["data_entrega"]["default"], "2023-12-31")
    
    def test_render_template(self):
        """Testa a renderização de um template"""
        # Primeiro carrega o template
        processed = self.manager.load_template(self.test_template)
        
        # Variáveis para renderização
        variables = {
            "especialidade": "marketing digital",
            "objetivo": "aumentar vendas",
            "estilo": "casual",
            "nome_cliente": "Empresa ABC",
            "email_cliente": "contato@empresaabc.com",
            "valor_orcamento": 5000,
            "data_entrega": "2024-06-30"
        }
        
        # Renderizar o template
        rendered = self.manager.render_template(self.test_template.id, variables)
        
        # Verificar se as substituições foram feitas
        self.assertIn("especializado em marketing digital", rendered)
        self.assertIn("aumentar vendas", rendered)
        self.assertIn("estilo de comunicação casual", rendered)
        self.assertIn("cliente Empresa ABC", rendered)
        self.assertIn("contato@empresaabc.com", rendered)
        self.assertIn("orçamento disponível é 5000", rendered)
        self.assertIn("data de entrega é 2024-06-30", rendered)
    
    def test_update_template(self):
        """Testa a atualização de um template"""
        # Primeiro carrega o template
        original = self.manager.load_template(self.test_template)
        
        # Criar uma versão atualizada
        updated_template = MockTemplate(
            id=self.test_template.id,  # Mesmo ID
            name="Template Atualizado",
            prompt_template="Você é um especialista em {{area}} com foco em {{sub_area}}."
        )
        
        # Atualizar o template
        updated = self.manager.update_template(updated_template)
        
        # Verificar se atualizou
        self.assertEqual(updated["name"], "Template Atualizado")
        self.assertEqual(updated["version"], 2)  # Nova versão
        
        # Verificar se as variáveis foram atualizadas
        self.assertIn("area", updated["variables"])
        self.assertIn("sub_area", updated["variables"])
        self.assertNotIn("especialidade", updated["variables"])
    
    def test_get_template_version(self):
        """Testa a obtenção de versões específicas de templates"""
        # Primeiro carrega o template
        original = self.manager.load_template(self.test_template)
        
        # Criar e atualizar duas vezes
        for i in range(2):
            updated_template = MockTemplate(
                id=self.test_template.id,
                name=f"Template Versão {i+2}",
                prompt_template=f"Versão {i+2} do template com {{var{i+2}}}."
            )
            self.manager.update_template(updated_template)
        
        # Obter versão original (1)
        v1 = self.manager.get_template_version(self.test_template.id, 1)
        # Obter versão 2
        v2 = self.manager.get_template_version(self.test_template.id, 2)
        # Obter versão 3
        v3 = self.manager.get_template_version(self.test_template.id, 3)
        # Obter versão mais recente
        latest = self.manager.get_template_version(self.test_template.id, 0)
        
        # Verificar versões
        self.assertEqual(v1["name"], "Template de Teste")
        self.assertEqual(v1["version"], 1)
        
        self.assertEqual(v2["name"], "Template Versão 2")
        self.assertEqual(v2["version"], 2)
        
        self.assertEqual(v3["name"], "Template Versão 3")
        self.assertEqual(v3["version"], 3)
        
        self.assertEqual(latest["version"], 3)  # A versão mais recente é a 3
    
    def test_validation(self):
        """Testa a validação de variáveis"""
        # Carregar um template com diferentes tipos de variáveis
        validation_template = MockTemplate(
            prompt_template="""
            Email: {{email:email}}
            Número: {{numero:number}}
            Data: {{data:date}}
            Escolha: {{opcao:choice=A,B,C}}
            """
        )
        
        processed = self.manager.load_template(validation_template)
        
        # Teste com valores válidos
        valid_variables = {
            "email": "teste@example.com",
            "numero": 42,
            "data": "2023-10-15",
            "opcao": "B"
        }
        
        # Não deve lançar exceção
        self.manager.render_template(validation_template.id, valid_variables)
        
        # Teste com email inválido
        invalid_email = valid_variables.copy()
        invalid_email["email"] = "not-an-email"
        
        with self.assertRaises(ValueError) as context:
            self.manager.render_template(validation_template.id, invalid_email)
        self.assertIn("Email", str(context.exception))
        
        # Teste com data inválida
        invalid_date = valid_variables.copy()
        invalid_date["data"] = "15/10/2023a"  # Formato inválido
        
        with self.assertRaises(ValueError) as context:
            self.manager.render_template(validation_template.id, invalid_date)
        self.assertIn("data", str(context.exception))
        
        # Teste com opção inválida
        invalid_choice = valid_variables.copy()
        invalid_choice["opcao"] = "D"  # Opção que não existe
        
        with self.assertRaises(ValueError) as context:
            self.manager.render_template(validation_template.id, invalid_choice)
        self.assertIn("opcao", str(context.exception))

class TestDepartmentTemplates(unittest.TestCase):
    """Testes para os templates departamentais predefinidos"""
    
    def test_marketing_templates(self):
        """Testa os templates de marketing"""
        templates = get_default_marketing_templates()
        
        # Verificar se existem templates
        self.assertGreater(len(templates), 0)
        
        # Verificar se os templates têm as propriedades esperadas
        for template in templates:
            self.assertIn("name", template)
            self.assertIn("description", template)
            self.assertIn("department", template)
            self.assertEqual(template["department"], TemplateDepartment.MARKETING)
            self.assertIn("prompt_template", template)
            self.assertIn("tools_config", template)
            self.assertIn("llm_config", template)
    
    def test_sales_templates(self):
        """Testa os templates de vendas"""
        templates = get_default_sales_templates()
        
        # Verificar se existem templates
        self.assertGreater(len(templates), 0)
        
        # Verificar se os templates têm as propriedades esperadas
        for template in templates:
            self.assertIn("name", template)
            self.assertIn("description", template)
            self.assertIn("department", template)
            self.assertEqual(template["department"], TemplateDepartment.SALES)
            self.assertIn("prompt_template", template)
            self.assertIn("tools_config", template)
            self.assertIn("llm_config", template)
    
    def test_finance_templates(self):
        """Testa os templates de finanças"""
        templates = get_default_finance_templates()
        
        # Verificar se existem templates
        self.assertGreater(len(templates), 0)
        
        # Verificar se os templates têm as propriedades esperadas
        for template in templates:
            self.assertIn("name", template)
            self.assertIn("description", template)
            self.assertIn("department", template)
            self.assertEqual(template["department"], TemplateDepartment.FINANCE)
            self.assertIn("prompt_template", template)
            self.assertIn("tools_config", template)
            self.assertIn("llm_config", template)

# Executar os testes
if __name__ == "__main__":
    unittest.main()