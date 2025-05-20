import os
import sys
import asyncio
import uuid
from datetime import datetime
import json
from typing import Dict, List, Any, Optional, Union

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Importar componentes necessários
from app.db.database import SessionLocal
from app.models.agent import Agent, AgentType
from app.models.template import Template, TemplateDepartment
from app.models.user import User, AuthProvider
from app.models.conversation import Conversation, ConversationStatus
from app.services.agent_service import get_agent_service
from app.services.template_service import get_template_service

# Classe para realizar o teste
class MultiAgentSystemTester:
    """
    Classe para testar o sistema multi-agentes completo.
    """
    
    def __init__(self):
        """Inicializa o testador."""
        self.db = SessionLocal()
        self.agent_service = get_agent_service(self.db)
        self.template_service = get_template_service(self.db)
        
        # IDs para entidades criadas
        self.user_id = None
        self.supervisor_id = None
        self.marketing_agent_id = None
        self.sales_agent_id = None
        self.finance_agent_id = None
        self.conversation_id = None
    
    async def setup(self):
        """Configura o ambiente de teste."""
        print("=== Configurando ambiente de teste ===")
        
        # 1. Criar usuário de teste
        user = self._create_test_user()
        self.user_id = user.id
        print(f"Usuário de teste criado: {user.name} ({user.id})")
        
        # 2. Buscar templates
        supervisor_template = self._get_template(TemplateDepartment.CUSTOM)
        marketing_template = self._get_template(TemplateDepartment.MARKETING)
        sales_template = self._get_template(TemplateDepartment.SALES)
        finance_template = self._get_template(TemplateDepartment.FINANCE)
        
        print(f"Templates encontrados:")
        print(f"  - Supervisor: {supervisor_template.name} ({supervisor_template.id})")
        print(f"  - Marketing: {marketing_template.name} ({marketing_template.id})")
        print(f"  - Vendas: {sales_template.name} ({sales_template.id})")
        print(f"  - Finanças: {finance_template.name} ({finance_template.id})")
        
        # 3. Criar agentes
        self.supervisor_id = self._create_agent(
            name="Supervisor de Teste",
            agent_type=AgentType.SUPERVISOR,
            template_id=supervisor_template.id,
            configuration={
                "company_name": "TechCorp",
                "industry": "Tecnologia",
                "priority": "Crescimento de vendas"
            }
        )
        
        self.marketing_agent_id = self._create_agent(
            name="Marketing de Teste",
            agent_type=AgentType.MARKETING,
            template_id=marketing_template.id,
            configuration={
                "company_name": "TechCorp",
                "primary_platform": "LinkedIn",
                "brand_tone": "profissional",
                "industry": "Tecnologia",
                "target_audience": "Empresas B2B",
                "differentials": "Tecnologia avançada, suporte premium",
                "metric_priority": "geração de leads",
                "especialidade": "Marketing Digital" 
                
            }
        )
        
        self.sales_agent_id = self._create_agent(
            name="Vendas de Teste",
            agent_type=AgentType.SALES,
            template_id=sales_template.id,
            configuration={
                "company_name": "TechCorp",
                "product_category": "Software empresarial",
                "products_list": "CRM, ERP, BI, Cloud Storage",
                "sales_style": "consultivo",
                "sales_priority": "construir relacionamentos de longo prazo",
                "pricing_policy": "assinatura mensal ou anual",
                "payment_terms": "mensal, trimestral ou anual com desconto",
                "delivery_time": "imediato após contrato",
                "return_policy": "garantia de 30 dias",
                "discount_level": "até 15%"
            }
        )
        
        self.finance_agent_id = self._create_agent(
            name="Finanças de Teste",
            agent_type=AgentType.FINANCE,
            template_id=finance_template.id,
            configuration={
                "analysis_type": "Gestão financeira",
                "company_name": "TechCorp",
                "industry": "Tecnologia",
                "competitors": "CompSoft, TechGiant, SoftCorp",
                "key_indicators": "ROI, margem de lucro, CAC, LTV",
                "analysis_period": "trimestral",
                "currency": "BRL",
                "accounting_standards": "IFRS",
                "analysis_methodology": "Indicadores-chave" 
            }
        )
        
        print(f"Agentes criados:")
        print(f"  - Supervisor: {self.supervisor_id}")
        print(f"  - Marketing: {self.marketing_agent_id}")
        print(f"  - Vendas: {self.sales_agent_id}")
        print(f"  - Finanças: {self.finance_agent_id}")
        
        # 4. Criar conversa para o teste
        self.conversation_id = self._create_conversation()
        print(f"Conversa criada: {self.conversation_id}")
        
        print("=== Ambiente de teste configurado com sucesso ===\n")
    
    async def run_test(self):
        """Executa o teste do sistema multi-agentes."""
        print("=== Executando teste do sistema multi-agentes ===")
        
        # Definir mensagens de teste para diferentes áreas
        test_messages = [
            "Olá, como posso melhorar a presença da empresa no LinkedIn para gerar mais leads?",
            "Estamos tendo dificuldades para fechar contratos grandes. Como podemos melhorar nossa abordagem de vendas?",
            "Precisamos analisar nosso ROI nas campanhas de marketing. Poderia preparar um relatório financeiro?",
            "Qual é a melhor forma de reduzir nosso CAC e aumentar o LTV dos clientes?"
        ]
        
        # 1. Testar o supervisor para classificação
        print("\n1. Teste do Supervisor para classificação:")
        
        for i, message in enumerate(test_messages):
            print(f"\nMensagem {i+1}: \"{message}\"")
            print("Processando com supervisor...")
            
            # Processar com o supervisor
            response = await self.agent_service.process_message(
                agent_id=self.supervisor_id,
                conversation_id=self.conversation_id,
                message=message
            )
            
            # Imprimir resposta e metadados relevantes
            print(f"Resposta: {response['agent_response']['message']['content'][:100]}...")
            
            if 'metadata' in response['agent_response']:
                selected_dept = response['agent_response']['metadata'].get('selected_department')
                selected_agent = response['agent_response']['metadata'].get('selected_agent')
                if selected_dept:
                    print(f"Departamento selecionado: {selected_dept}")
                if selected_agent:
                    print(f"Agente selecionado: {selected_agent}")
        
        # 2. Testar agentes específicos
        print("\n2. Teste de agentes específicos:")
        
        # Marketing
        marketing_message = "Precisamos uma estratégia para aumentar nosso engajamento no LinkedIn e gerar mais leads qualificados para o nosso produto de CRM."
        print(f"\nTestando agente de Marketing com mensagem: \"{marketing_message}\"")
        
        marketing_response = await self.agent_service.process_message(
            agent_id=self.marketing_agent_id,
            conversation_id=self.conversation_id,
            message=marketing_message
        )
        
        print(f"Resposta: {marketing_response['agent_response']['message']['content'][:200]}...")
        print(f"Ações: {json.dumps(marketing_response['agent_response'].get('actions', []), indent=2)[:200]}...")
        
        # Vendas
        sales_message = "Estamos tendo dificuldade em converter leads para nosso produto ERP. Como podemos melhorar nossa abordagem de vendas e superar objeções sobre o preço?"
        print(f"\nTestando agente de Vendas com mensagem: \"{sales_message}\"")
        
        sales_response = await self.agent_service.process_message(
            agent_id=self.sales_agent_id,
            conversation_id=self.conversation_id,
            message=sales_message
        )
        
        print(f"Resposta: {sales_response['agent_response']['message']['content'][:200]}...")
        print(f"Ações: {json.dumps(sales_response['agent_response'].get('actions', []), indent=2)[:200]}...")
        
        # Finanças
        finance_message = "Precisamos analisar o ROI das nossas ferramentas de marketing. Pode nos ajudar a preparar um relatório financeiro para o último trimestre?"
        print(f"\nTestando agente de Finanças com mensagem: \"{finance_message}\"")
        
        finance_response = await self.agent_service.process_message(
            agent_id=self.finance_agent_id,
            conversation_id=self.conversation_id,
            message=finance_message
        )
        
        print(f"Resposta: {finance_response['agent_response']['message']['content'][:200]}...")
        print(f"Ações: {json.dumps(finance_response['agent_response'].get('actions', []), indent=2)[:200]}...")
        
        print("\n=== Teste do sistema multi-agentes concluído com sucesso ===")
    
    def cleanup(self):
        """Limpa os recursos criados para o teste."""
        print("\n=== Limpando recursos de teste ===")
        
        try:
            # Desativar agentes
            if self.supervisor_id:
                self.agent_service.delete_agent(self.supervisor_id)
                print(f"Agente supervisor desativado: {self.supervisor_id}")
            
            if self.marketing_agent_id:
                self.agent_service.delete_agent(self.marketing_agent_id)
                print(f"Agente de marketing desativado: {self.marketing_agent_id}")
            
            if self.sales_agent_id:
                self.agent_service.delete_agent(self.sales_agent_id)
                print(f"Agente de vendas desativado: {self.sales_agent_id}")
            
            if self.finance_agent_id:
                self.agent_service.delete_agent(self.finance_agent_id)
                print(f"Agente financeiro desativado: {self.finance_agent_id}")
            
            # Arquivar conversa
            if self.conversation_id:
                conversation = self.db.query(Conversation).filter(Conversation.id == self.conversation_id).first()
                if conversation:
                    conversation.status = ConversationStatus.ARCHIVED
                    self.db.commit()
                    print(f"Conversa arquivada: {self.conversation_id}")
            
            print("=== Recursos de teste limpos com sucesso ===")
            
        finally:
            self.db.close()
    
    def _create_test_user(self) -> User:
        """Cria ou obtém um usuário de teste."""
        # Verificar se já existe
        user = self.db.query(User).filter(User.email == "teste@example.com").first()
        
        if user:
            return user
        
        # Criar novo usuário
        from app.core.security import get_password_hash
        
        user = User(
            id=str(uuid.uuid4()),
            email="teste@example.com",
            name="Usuário de Teste",
            hashed_password=get_password_hash("senha123"),
            provider=AuthProvider.LOCAL,
            is_verified=True,
            is_active=True
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def _get_template(self, department: TemplateDepartment) -> Template:
        """Obtém um template público para o departamento especificado."""
        template = self.db.query(Template).filter(
            Template.department == department,
            Template.is_public == True
        ).first()
        
        if not template:
            raise ValueError(f"Nenhum template público encontrado para o departamento {department}")
        
        return template
    
    def _create_agent(self, name: str, agent_type: AgentType, template_id: str, configuration: Dict) -> str:
        """Cria um agente e retorna seu ID."""
        agent = self.agent_service.create_agent(
            user_id=self.user_id,
            name=name,
            description=f"Agente de teste para {agent_type.value}",
            agent_type=agent_type,
            template_id=template_id,
            configuration=configuration
        )
        
        return agent.id
    
    def _create_conversation(self) -> str:
        """Cria uma conversa para o teste."""
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title="Conversa de Teste Multi-Agentes",
            user_id=self.user_id,
            agent_id=self.supervisor_id,
            status=ConversationStatus.ACTIVE,
            metadata={"test": True}
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation.id

# Função principal para executar o teste
async def main():
    """Função principal para executar o teste."""
    print("=" * 80)
    print(" TESTE DO SISTEMA MULTI-AGENTES ".center(80, "="))
    print("=" * 80)
    
    tester = MultiAgentSystemTester()
    
    try:
        # Configurar o ambiente
        await tester.setup()
        
        # Executar os testes
        await tester.run_test()
        
    except Exception as e:
        print(f"\nERRO durante o teste: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Limpar recursos
        tester.cleanup()
        
    print("\n" + "=" * 80)
    print(" FIM DO TESTE ".center(80, "="))
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())