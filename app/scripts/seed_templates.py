# app/scripts/seed_templates.py
import os
import sys
import asyncio
from sqlalchemy.orm import Session

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Importar componentes necessários
from app.db.database import SessionLocal
from app.models.template import Template, TemplateDepartment
from app.services.template_service import get_template_service
from app.templates.marketing import get_default_marketing_templates
from app.templates.sales import get_default_sales_templates
from app.templates.finance import get_default_finance_templates

def seed_templates():
    """
    Popula o banco de dados com templates predefinidos para cada departamento.
    """
    # Obter sessão do banco
    db = SessionLocal()
    
    try:
        # Obter o serviço de templates
        template_service = get_template_service(db)
        
        # Templates de supervisão
        supervisor_template = {
            "name": "Agente Supervisor",
            "description": "Template para agentes supervisores que coordenam outros agentes",
            "department": TemplateDepartment.CUSTOM,
            "is_public": True,
            "prompt_template": """Você é um agente supervisor responsável por coordenar uma equipe de agentes especializados.

Sua principal função é:
1. Analisar solicitações dos usuários
2. Determinar qual agente especializado é mais adequado para resolver cada problema
3. Coordenar o fluxo de trabalho entre múltiplos agentes quando necessário
4. Garantir que todas as tarefas sejam concluídas corretamente

Você coordena agentes dos seguintes departamentos:
- Marketing: Especialistas em marketing, branding, comunicação e redes sociais
- Vendas: Especialistas em vendas, negociação, prospecção e gestão de clientes
- Financeiro: Especialistas em finanças, contabilidade, orçamentos e análise financeira

Ao receber uma mensagem:
1. Analise cuidadosamente o conteúdo e intenção
2. Identifique a qual departamento a solicitação se refere
3. Direcione para o agente mais adequado
4. Monitore a execução e forneça feedback

Como supervisor, você deve ser:
- Eficiente em alocar recursos
- Preciso na análise de solicitações
- Claro em suas comunicações
- Focado em resultados positivos

Nome da empresa: {{company_name}}
Indústria/segmento: {{industry}}
Prioridade atual: {{priority}}
""",
            "tools_config": {
                "allowed_tools": ["calendar", "task_manager", "email"]
            },
            "llm_config": {
                "temperature": 0.3,
                "max_tokens": 1024
            }
        }
        
        print("Populando templates do sistema...")
        
        # Verificar se o template de supervisor já existe
        existing = db.query(Template).filter(
            Template.name == supervisor_template["name"],
            Template.is_public == True,
            Template.user_id == None
        ).first()
        
        if not existing:
            template_service.create_template(
                name=supervisor_template["name"],
                description=supervisor_template["description"],
                department=supervisor_template["department"],
                is_public=supervisor_template["is_public"],
                prompt_template=supervisor_template["prompt_template"],
                tools_config=supervisor_template["tools_config"],
                llm_config=supervisor_template["llm_config"]
            )
            print(f"Template de supervisor criado: {supervisor_template['name']}")
        else:
            print(f"Template de supervisor já existe: {existing.name}")
        
        # Marketing templates
        print("\nPopulando templates de marketing...")
        marketing_templates = get_default_marketing_templates()
        
        for template_data in marketing_templates:
            existing = db.query(Template).filter(
                Template.name == template_data["name"],
                Template.is_public == True,
                Template.user_id == None
            ).first()
            
            if not existing:
                template_service.create_template(
                    name=template_data["name"],
                    description=template_data["description"],
                    department=template_data["department"],
                    is_public=template_data["is_public"],
                    prompt_template=template_data["prompt_template"],
                    tools_config=template_data["tools_config"],
                    llm_config=template_data["llm_config"]
                )
                print(f"Template de marketing criado: {template_data['name']}")
            else:
                print(f"Template de marketing já existe: {existing.name}")
        
        # Sales templates
        print("\nPopulando templates de vendas...")
        sales_templates = get_default_sales_templates()
        
        for template_data in sales_templates:
            existing = db.query(Template).filter(
                Template.name == template_data["name"],
                Template.is_public == True,
                Template.user_id == None
            ).first()
            
            if not existing:
                template_service.create_template(
                    name=template_data["name"],
                    description=template_data["description"],
                    department=template_data["department"],
                    is_public=template_data["is_public"],
                    prompt_template=template_data["prompt_template"],
                    tools_config=template_data["tools_config"],
                    llm_config=template_data["llm_config"]
                )
                print(f"Template de vendas criado: {template_data['name']}")
            else:
                print(f"Template de vendas já existe: {existing.name}")
        
        # Finance templates
        print("\nPopulando templates de finanças...")
        finance_templates = get_default_finance_templates()
        
        for template_data in finance_templates:
            existing = db.query(Template).filter(
                Template.name == template_data["name"],
                Template.is_public == True,
                Template.user_id == None
            ).first()
            
            if not existing:
                template_service.create_template(
                    name=template_data["name"],
                    description=template_data["description"],
                    department=template_data["department"],
                    is_public=template_data["is_public"],
                    prompt_template=template_data["prompt_template"],
                    tools_config=template_data["tools_config"],
                    llm_config=template_data["llm_config"]
                )
                print(f"Template de finanças criado: {template_data['name']}")
            else:
                print(f"Template de finanças já existe: {existing.name}")
        
        print("\nProcesso de seed concluído com sucesso!")
        
    except Exception as e:
        print(f"Erro durante seed de templates: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_templates()