#!/usr/bin/env python3
# app/scripts/complete_setup.py - Versão Corrigida
"""
Script completo para setup e teste do sistema multi-agentes.
Inclui criação de banco, população de dados e testes funcionais.
"""

import os
import sys

# CORREÇÃO: Configurar o PYTHONPATH corretamente
# Obter o diretório do script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Subir dois níveis para chegar à pasta backend
backend_dir = os.path.dirname(os.path.dirname(script_dir))
# Adicionar ao Python path
sys.path.insert(0, backend_dir)

print(f"📍 Script directory: {script_dir}")
print(f"📍 Backend directory: {backend_dir}")
print(f"📍 Python path configurado: {backend_dir}")

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

# Agora podemos importar os módulos normalmente
try:
    from sqlalchemy import create_engine, text
    from app.config import settings
    from app.db.database import SessionLocal, Base
    from app.models.user import User, AuthProvider
    from app.models.template import Template, TemplateDepartment
    from app.models.agent import Agent, AgentType
    from app.models.conversation import Conversation, ConversationStatus
    from app.models.message import Message, MessageRole
    from app.services.agent_service import get_agent_service
    from app.services.template_service import get_template_service
    from app.core.security import get_password_hash
    print("✅ Todos os módulos importados com sucesso!")
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("\n🔧 Possíveis soluções:")
    print("1. Certifique-se de estar na pasta backend")
    print("2. Verifique se o ambiente virtual está ativado")
    print("3. Execute: pip install -r requirements.txt")
    sys.exit(1)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemSetup:
    """
    Classe principal para setup completo do sistema.
    """
    
    def __init__(self):
        """Inicializa o setup."""
        try:
            self.db = SessionLocal()
            self.engine = create_engine(settings.DATABASE_URL)
            self.agent_service = get_agent_service(self.db)
            self.template_service = get_template_service(self.db)
            
            # IDs criados durante o setup
            self.demo_user_id = None
            self.template_ids = {}
            self.agent_ids = {}
            self.conversation_ids = []
            
            print("✅ SystemSetup inicializado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao inicializar SystemSetup: {e}")
            raise
    
    async def run_complete_setup(self):
        """
        Executa o setup completo do sistema.
        """
        logger.info("🚀 Iniciando setup completo do sistema multi-agentes")
        
        try:
            # 1. Setup do banco de dados
            logger.info("📊 Configurando banco de dados...")
            await self._setup_database()
            
            # 2. Criar usuário demo
            logger.info("👤 Criando usuário demo...")
            await self._create_demo_user()
            
            # 3. Criar templates padrão
            logger.info("📋 Criando templates padrão...")
            await self._create_default_templates()
            
            # 4. Criar agentes demo
            logger.info("🤖 Criando agentes demo...")
            await self._create_demo_agents()
            
            # 5. Executar testes funcionais
            logger.info("🧪 Executando testes funcionais...")
            await self._run_functional_tests()
            
            # 6. Relatório final
            logger.info("📈 Gerando relatório final...")
            await self._generate_final_report()
            
            logger.info("✅ Setup completo finalizado com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro durante o setup: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            self.db.close()
    
    async def _setup_database(self):
        """Configura o banco de dados."""
        logger.info("   - Verificando conexão com o banco...")
        
        try:
            with self.engine.connect() as connection:
                # Testar conexão
                connection.execute(text("SELECT 1"))
                logger.info("   ✓ Conexão com banco de dados estabelecida")
                
                # Criar extensão vector
                try:
                    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    connection.commit()
                    logger.info("   ✓ Extensão pgvector criada/verificada")
                except Exception as e:
                    logger.warning(f"   ⚠️ Não foi possível criar extensão pgvector: {e}")
                    logger.info("   ℹ️ Continuando sem pgvector...")
                
                # Criar todas as tabelas
                Base.metadata.create_all(bind=self.engine)
                logger.info("   ✓ Tabelas do banco criadas/verificadas")
                
                # Criar índices de performance
                performance_indices = [
                    "CREATE INDEX IF NOT EXISTS idx_agents_user_type ON agents(user_id, type);",
                    "CREATE INDEX IF NOT EXISTS idx_conversations_user_agent ON conversations(user_id, agent_id);",
                    "CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at);",
                    "CREATE INDEX IF NOT EXISTS idx_templates_dept_public ON templates(department, is_public);"
                ]
                
                for index_sql in performance_indices:
                    try:
                        connection.execute(text(index_sql))
                    except Exception as e:
                        logger.warning(f"   ⚠️ Erro ao criar índice: {e}")
                
                connection.commit()
                logger.info("   ✓ Índices de performance criados")
                
        except Exception as e:
            logger.error(f"   ❌ Erro na configuração do banco: {str(e)}")
            raise
    
    async def _create_demo_user(self):
        """Cria um usuário demo para testes."""
        demo_email = "demo@techcorp.com"
        
        # Verificar se já existe
        existing_user = self.db.query(User).filter(User.email == demo_email).first()
        
        if existing_user:
            self.demo_user_id = existing_user.id
            logger.info(f"   ✓ Usuário demo já existe: {demo_email}")
            return
        
        # Criar novo usuário
        demo_user = User(
            id=str(uuid.uuid4()),
            email=demo_email,
            name="Demo User - TechCorp",
            hashed_password=get_password_hash("demo123"),
            provider=AuthProvider.LOCAL,
            is_verified=True,
            is_active=True
        )
        
        self.db.add(demo_user)
        self.db.commit()
        self.db.refresh(demo_user)
        
        self.demo_user_id = demo_user.id
        logger.info(f"   ✓ Usuário demo criado: {demo_email} (ID: {self.demo_user_id})")
    
    async def _create_default_templates(self):
        """Cria templates padrão para todos os departamentos."""
        templates_config = {
            "supervisor": {
                "name": "Supervisor Geral",
                "description": "Template para agente supervisor que coordena outros agentes",
                "department": TemplateDepartment.CUSTOM,
                "prompt_template": """Você é um supervisor inteligente da {{company_name}}, especializada em {{industry}}.

Sua função é analisar solicitações e direcionar para o agente mais adequado:

🎯 MARKETING: Campanhas, redes sociais, branding, conteúdo, análise de mercado
💰 VENDAS: Prospecção, negociação, propostas, relacionamento com clientes
📊 FINANÇAS: Análise financeira, orçamentos, relatórios, indicadores, ROI

Ao receber uma solicitação:
1. Analise o conteúdo cuidadosamente
2. Identifique o departamento mais adequado
3. Explique brevemente sua decisão
4. Direcione para o agente especializado

Empresa: {{company_name}}
Setor: {{industry}}
Prioridade atual: {{priority}}""",
                "tools_config": {"allowed_tools": ["routing", "analysis"]},
                "llm_config": {"temperature": 0.3, "max_tokens": 1024}
            },
            
            "marketing": {
                "name": "Especialista em Marketing Digital",
                "description": "Agente especializado em marketing digital e estratégias de crescimento",
                "department": TemplateDepartment.MARKETING,
                "prompt_template": """Você é um especialista em marketing digital da {{company_name}}.

🎯 ESPECIALIDADES:
- Marketing Digital e Redes Sociais (foco em {{primary_platform}})
- Estratégias de Conteúdo e SEO
- Campanhas de Performance e Branding
- Análise de Métricas e ROI

📊 SOBRE A EMPRESA:
- Empresa: {{company_name}}
- Setor: {{industry}}
- Tom da marca: {{brand_tone}}
- Público-alvo: {{target_audience}}
- Diferenciais: {{differentials}}

🎯 ABORDAGEM:
Seja estratégico, criativo e focado em resultados. Sempre considere o {{metric_priority}} como indicador principal de sucesso.

Como especialista em {{especialidade}}, forneça insights práticos e acionáveis.""",
                "tools_config": {"allowed_tools": ["social_media", "analytics", "content_tools"]},
                "llm_config": {"temperature": 0.7, "max_tokens": 1536}
            },
            
            "sales": {
                "name": "Consultor de Vendas B2B",
                "description": "Agente especializado em vendas consultivas e relacionamento com clientes",
                "department": TemplateDepartment.SALES,
                "prompt_template": """Você é um consultor de vendas especialista da {{company_name}}.

💼 PORTFÓLIO:
- Categoria: {{product_category}}
- Produtos: {{products_list}}
- Estilo de vendas: {{sales_style}}
- Prioridade: {{sales_priority}}

🤝 POLÍTICA COMERCIAL:
- Preços: {{pricing_policy}}
- Pagamento: {{payment_terms}}
- Entrega: {{delivery_time}}
- Devoluções: {{return_policy}}
- Descontos: {{discount_level}}

🎯 ABORDAGEM:
Use uma abordagem consultiva, identifique necessidades reais, apresente soluções relevantes e conduza naturalmente ao fechamento.

Seja um parceiro estratégico, não apenas um vendedor.""",
                "tools_config": {"allowed_tools": ["crm", "product_catalog", "proposal_generator"]},
                "llm_config": {"temperature": 0.6, "max_tokens": 1024}
            },
            
            "finance": {
                "name": "Analista Financeiro Sênior",
                "description": "Agente especializado em análises financeiras e planejamento estratégico",
                "department": TemplateDepartment.FINANCE,
                "prompt_template": """Você é um analista financeiro sênior da {{company_name}}.

📊 ESPECIALIZAÇÃO:
- Tipo de análise: {{analysis_type}}
- Metodologia: {{analysis_methodology}}
- Período de análise: {{analysis_period}}
- Moeda: {{currency}}

🏢 CONTEXTO DA EMPRESA:
- Empresa: {{company_name}}
- Setor: {{industry}}
- Concorrentes: {{competitors}}
- Indicadores-chave: {{key_indicators}}
- Normas contábeis: {{accounting_standards}}

🎯 ABORDAGEM:
Seja preciso, analítico e estratégico. Forneça insights baseados em dados, identifique tendências e recomende ações concretas.

Sempre contextualize números e explique o impacto no negócio.""",
                "tools_config": {"allowed_tools": ["financial_calculator", "report_generator", "data_analyzer"]},
                "llm_config": {"temperature": 0.3, "max_tokens": 1536}
            }
        }
        
        for template_key, config in templates_config.items():
            # Verificar se já existe
            existing = self.db.query(Template).filter(
                Template.name == config["name"],
                Template.is_public == True,
                Template.user_id == None
            ).first()
            
            if existing:
                self.template_ids[template_key] = existing.id
                logger.info(f"   ✓ Template {template_key} já existe")
                continue
            
            # Criar template
            template = self.template_service.create_template(
                name=config["name"],
                description=config["description"],
                department=config["department"],
                is_public=True,
                user_id=None,  # Template do sistema
                prompt_template=config["prompt_template"],
                tools_config=config["tools_config"],
                llm_config=config["llm_config"]
            )
            
            self.template_ids[template_key] = template.id
            logger.info(f"   ✓ Template {template_key} criado: {template.name}")
    
    async def _create_demo_agents(self):
        """Cria agentes demo para demonstração."""
        agents_config = [
            {
                "key": "supervisor",
                "name": "Coordenador TechCorp",
                "type": AgentType.SUPERVISOR,
                "template": "supervisor",
                "config": {
                    "company_name": "TechCorp Solutions",
                    "industry": "Tecnologia",
                    "priority": "Crescimento sustentável e inovação"
                }
            },
            {
                "key": "marketing",
                "name": "Sarah - Marketing Digital",
                "type": AgentType.MARKETING,
                "template": "marketing",
                "config": {
                    "company_name": "TechCorp Solutions",
                    "industry": "Tecnologia",
                    "primary_platform": "LinkedIn",
                    "brand_tone": "profissional e inovador",
                    "target_audience": "Empresas de médio e grande porte",
                    "differentials": "Tecnologia de ponta, suporte premium, ROI comprovado",
                    "metric_priority": "geração de leads qualificados",
                    "especialidade": "Marketing B2B e Growth Hacking"
                }
            },
            {
                "key": "sales",
                "name": "Carlos - Consultor de Vendas",
                "type": AgentType.SALES,
                "template": "sales",
                "config": {
                    "company_name": "TechCorp Solutions",
                    "product_category": "Soluções tecnológicas empresariais",
                    "products_list": "CRM personalizado, ERP integrado, BI Analytics, Cloud Infrastructure",
                    "sales_style": "consultivo e estratégico",
                    "sales_priority": "construir relacionamentos de longo prazo",
                    "pricing_policy": "valor baseado em ROI do cliente",
                    "payment_terms": "flexível: mensal, trimestral ou anual",
                    "delivery_time": "implantação em 30-90 dias",
                    "return_policy": "garantia de satisfação de 60 dias",
                    "discount_level": "até 20% para contratos anuais"
                }
            },
            {
                "key": "finance",
                "name": "Ana - Analista Financeira",
                "type": AgentType.FINANCE,
                "template": "finance",
                "config": {
                    "company_name": "TechCorp Solutions",
                    "industry": "Tecnologia",
                    "analysis_type": "Performance financeira e ROI",
                    "analysis_methodology": "Análise comparativa e projeções",
                    "analysis_period": "mensal com projeções trimestrais",
                    "currency": "BRL",
                    "competitors": "SoftTech, InnovaCorp, TechGlobal",
                    "key_indicators": "ARR, CAC, LTV, Churn Rate, Margem Bruta",
                    "accounting_standards": "IFRS"
                }
            }
        ]
        
        for agent_config in agents_config:
            try:
                agent = self.agent_service.create_agent(
                    user_id=self.demo_user_id,
                    name=agent_config["name"],
                    description=f"Agente demo para {agent_config['type'].value}",
                    agent_type=agent_config["type"],
                    template_id=self.template_ids[agent_config["template"]],
                    configuration=agent_config["config"]
                )
                
                self.agent_ids[agent_config["key"]] = agent.id
                logger.info(f"   ✓ Agente criado: {agent.name} ({agent_config['type'].value})")
            except Exception as e:
                logger.error(f"   ❌ Erro ao criar agente {agent_config['name']}: {e}")
    
    async def _run_functional_tests(self):
        """Executa testes funcionais do sistema."""
        test_scenarios = [
            {
                "description": "Solicitação de campanha de marketing",
                "message": "Preciso de uma estratégia completa para lançar nosso novo produto CRM no LinkedIn. Qual seria a melhor abordagem?",
                "expected_department": "marketing"
            },
            {
                "description": "Consulta sobre vendas",
                "message": "Como posso melhorar nossa taxa de conversão de leads? Estamos com dificuldade no fechamento de vendas.",
                "expected_department": "sales"
            },
            {
                "description": "Análise financeira",
                "message": "Preciso de uma análise do ROI das nossas campanhas de marketing do último trimestre. Pode me ajudar?",
                "expected_department": "finance"
            }
        ]
        
        for i, scenario in enumerate(test_scenarios, 1):
            logger.info(f"   🧪 Teste {i}: {scenario['description']}")
            
            try:
                # Criar conversa para o teste
                conversation = Conversation(
                    id=str(uuid.uuid4()),
                    title=f"Teste Funcional {i}",
                    user_id=self.demo_user_id,
                    agent_id=self.agent_ids["supervisor"],
                    status=ConversationStatus.ACTIVE,
                    meta_data={"test": True, "scenario": scenario["description"]}
                )
                
                self.db.add(conversation)
                self.db.commit()
                self.db.refresh(conversation)
                self.conversation_ids.append(conversation.id)
                
                # Processar mensagem com o supervisor
                try:
                    response = await self.agent_service.process_message(
                        agent_id=self.agent_ids["supervisor"],
                        conversation_id=conversation.id,
                        message=scenario["message"]
                    )
                    
                    # Verificar resposta
                    agent_response = response.get("agent_response", {})
                    if agent_response:
                        logger.info(f"     ✓ Supervisor respondeu: {agent_response.get('message', {}).get('content', '')[:100]}...")
                        
                        # Verificar se direcionou corretamente
                        metadata = agent_response.get("metadata", {})
                        selected_dept = metadata.get("selected_department")
                        
                        if selected_dept == scenario["expected_department"]:
                            logger.info(f"     ✓ Direcionamento correto: {selected_dept}")
                        else:
                            logger.warning(f"     ⚠️ Direcionamento inesperado: {selected_dept} (esperado: {scenario['expected_department']})")
                    else:
                        logger.error(f"     ❌ Nenhuma resposta recebida")
                        
                except Exception as e:
                    logger.error(f"     ❌ Erro ao processar mensagem: {e}")
                
                # Pequena pausa entre testes
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"     ❌ Erro no teste {i}: {str(e)}")
    
    async def _generate_final_report(self):
        """Gera relatório final do setup."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "demo_user_id": self.demo_user_id,
            "templates_created": len(self.template_ids),
            "agents_created": len(self.agent_ids),
            "test_conversations": len(self.conversation_ids),
            "components": {
                "database": "✅ Configurado",
                "templates": "✅ Criados",
                "agents": "✅ Criados",
                "tests": "✅ Executados"
            }
        }
        
        logger.info("📈 RELATÓRIO FINAL DO SETUP:")
        logger.info(f"   👤 Usuário demo: {self.demo_user_id}")
        logger.info(f"   📋 Templates: {list(self.template_ids.keys())}")
        logger.info(f"   🤖 Agentes: {list(self.agent_ids.keys())}")
        logger.info(f"   💬 Conversas de teste: {len(self.conversation_ids)}")
        
        # Salvar relatório em arquivo
        import json
        try:
            report_path = os.path.join(backend_dir, "setup_report.json")
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"   📄 Relatório salvo em: {report_path}")
        except Exception as e:
            logger.error(f"   ❌ Erro ao salvar relatório: {str(e)}")

async def main():
    """Função principal."""
    print("🚀 SETUP COMPLETO DO SISTEMA MULTI-AGENTES")
    print("=" * 60)
    
    try:
        setup = SystemSetup()
        await setup.run_complete_setup()
        
        print("\n✅ SETUP CONCLUÍDO COM SUCESSO!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Acesse a aplicação em: http://localhost:8000")
        print("2. Faça login com: demo@techcorp.com / demo123")
        print("3. Teste os agentes criados")
        print("4. Visualize métricas em: http://localhost:8000/api/metrics")
        print("5. Explore a documentação da API em: http://localhost:8000/docs")
        
    except Exception as e:
        print(f"\n❌ Erro durante o setup: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))