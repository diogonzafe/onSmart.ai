"""
Script para testar a criação e relacionamentos das tabelas definidas na Etapa 1.
Execute este script após implementar as estruturas de dados e iniciar o banco de dados.
"""
import sys
import uuid
from datetime import datetime
import json
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

# Adicione o diretório raiz ao path para importar os módulos
# Identifica o caminho do diretório backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

print(f"Backend path: {backend_dir}")
print(f"Python path: {sys.path}")

import os

from app.db.database import engine, Base, SessionLocal
from app.models.user import User, AuthProvider
from app.models.agent import Agent, AgentType
from app.models.template import Template, TemplateDepartment
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.models.embedding import MessageEmbedding
from app.models.tool import Tool, ToolType
from app.models.agent_tool_mapping import AgentToolMapping
from app.models.metrics import AgentMetrics, UserFeedback

def print_separator(title=None):
    """Imprime um separador com título opcional para melhor legibilidade."""
    print("\n" + "="*80)
    if title:
        print(f" {title} ".center(80, "-"))
    print("="*80 + "\n")

def check_tables():
    """Verifica se todas as tabelas foram criadas no banco de dados."""
    print_separator("VERIFICAÇÃO DE TABELAS")
    
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    expected_tables = [
        "users", "agents", "templates", "conversations", "messages",
        "message_embeddings", "tools", "agent_tool_mappings",
        "agent_metrics", "user_feedback"
    ]
    
    print("Tabelas encontradas no banco de dados:")
    for table in table_names:
        print(f"  - {table}")
    
    print("\nVerificação de tabelas esperadas:")
    all_tables_found = True
    for table in expected_tables:
        if table in table_names:
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table}")
            all_tables_found = False
    
    if all_tables_found:
        print("\n✅ Todas as tabelas esperadas foram criadas com sucesso.")
    else:
        print("\n❌ Algumas tabelas esperadas não foram encontradas.")

def check_vector_extension():
    """Verifica se a extensão pgvector está ativada."""
    print_separator("VERIFICAÇÃO DA EXTENSÃO PGVECTOR")
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        extensions = result.fetchall()
        
        if extensions:
            print("✅ Extensão pgvector está instalada e ativa.")
        else:
            print("❌ Extensão pgvector NÃO está instalada.")

def insert_test_data():
    """Insere dados de teste para verificar relacionamentos entre tabelas."""
    print_separator("INSERÇÃO DE DADOS DE TESTE")
    
    # Gera IDs únicos para os registros
    user_id = str(uuid.uuid4())
    template_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())
    
    with SessionLocal() as db:
        # Verificar se já existe um usuário para teste
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if existing_user:
            user_id = existing_user.id
            print(f"✅ Usuário de teste já existe: {existing_user.email}")
        else:
            # Criar usuário de teste
            user = User(
                id=user_id,
                email="test@example.com",
                name="Usuário de Teste",
                hashed_password="$2b$12$EYyNiHf.U1pubMZ9g1xX6OBNFUf9/qSCzGGI0ZXvLsLK6VuOr6h.i",  # "password"
                provider=AuthProvider.LOCAL,
                is_verified=True,
                is_active=True
            )
            db.add(user)
            db.flush()
            print(f"✅ Usuário de teste criado: {user.email}")
        
        # Criar template de teste
        template = Template(
            id=template_id,
            name="Template de Marketing",
            description="Template para agentes de marketing",
            department=TemplateDepartment.MARKETING,
            is_public=True,
            user_id=user_id,
            prompt_template="Você é um agente de marketing especializado em {{especialidade}}.",
            tools_config={"allowed_tools": ["email", "calendar"]},
            llm_config={"model": "mistral", "temperature": 0.7}
        )
        db.add(template)
        db.flush()
        print(f"✅ Template criado: {template.name}")
        
        # Criar agente de teste
        agent = Agent(
            id=agent_id,
            name="Agente de Marketing",
            description="Agente para campanhas de marketing",
            user_id=user_id,
            type=AgentType.MARKETING,
            template_id=template_id,
            configuration={"especialidade": "redes sociais"}
        )
        db.add(agent)
        db.flush()
        print(f"✅ Agente criado: {agent.name}")
        
        # Criar ferramenta de teste
        tool = Tool(
            id=tool_id,
            name="Email Marketing",
            description="Ferramenta para envio de emails",
            type=ToolType.EMAIL,
            user_id=user_id,
            configuration={"smtp_server": "smtp.example.com"}
        )
        db.add(tool)
        db.flush()
        print(f"✅ Ferramenta criada: {tool.name}")
        
        # Criar mapeamento agente-ferramenta
        mapping = AgentToolMapping(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tool_id=tool_id,
            permissions={"allowed": ["read", "write"]}
        )
        db.add(mapping)
        db.flush()
        print(f"✅ Mapeamento agente-ferramenta criado")
        
        # Criar conversa de teste
        conversation = Conversation(
            id=conversation_id,
            title="Conversa de teste",
            user_id=user_id,
            agent_id=agent_id,
            status=ConversationStatus.ACTIVE,
            metadata={"context": "campanha de verão"}
        )
        db.add(conversation)
        db.flush()
        print(f"✅ Conversa criada: {conversation.title}")
        
        # Criar mensagens de teste
        human_message = Message(
            id=message_id,
            conversation_id=conversation_id,
            role=MessageRole.HUMAN,
            content="Como podemos melhorar nossa presença nas redes sociais?",
            metadata={"device": "web"}
        )
        db.add(human_message)
        db.flush()
        print(f"✅ Mensagem humana criada")
        
        agent_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=MessageRole.AGENT,
            content="Podemos começar criando um calendário de conteúdo consistente e engajador para as principais plataformas.",
            metadata={"tools_used": ["calendar"]}
        )
        db.add(agent_message)
        db.flush()
        print(f"✅ Mensagem do agente criada")
        
        # Criar embedding de teste (vetor de exemplo)
        sample_vector = [0.1] * 1536  # Vetor simples para teste
        embedding = MessageEmbedding(
            id=str(uuid.uuid4()),
            message_id=message_id,
            embedding=sample_vector
        )
        
        try:
            db.add(embedding)
            db.flush()
            print(f"✅ Embedding criado com sucesso")
        except Exception as e:
            print(f"❌ Erro ao criar embedding: {str(e)}")
        
        # Criar métricas de teste
        metrics = AgentMetrics(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=conversation_id,
            response_time=0.75,
            tools_used={"calendar": 1},
            llm_tokens=250
        )
        db.add(metrics)
        db.flush()
        print(f"✅ Métricas criadas")
        
        # Criar feedback de teste
        feedback = UserFeedback(
            id=str(uuid.uuid4()),
            message_id=agent_message.id,
            rating=4,
            feedback_text="Resposta útil e específica"
        )
        db.add(feedback)
        
        # Commit todas as alterações
        db.commit()
        print(f"✅ Dados de teste salvos no banco de dados")

def check_relationships():
    """Verifica se os relacionamentos entre as tabelas estão funcionando corretamente."""
    print_separator("VERIFICAÇÃO DE RELACIONAMENTOS")
    
    with SessionLocal() as db:
        # Buscar um usuário e verificar seus relacionamentos
        user = db.query(User).filter(User.email == "test@example.com").first()
        
        if not user:
            print("❌ Usuário de teste não encontrado")
            return
        
        # Verificar agentes do usuário
        agents = db.query(Agent).filter(Agent.user_id == user.id).all()
        print(f"Agentes do usuário ({len(agents)}):")
        for agent in agents:
            print(f"  - {agent.name} ({agent.type.value})")
        
        if not agents:
            print("❌ Nenhum agente encontrado para o usuário")
            return
            
        agent = agents[0]
        
        # Verificar template do agente
        template = db.query(Template).filter(Template.id == agent.template_id).first()
        if template:
            print(f"\nTemplate do agente:")
            print(f"  - {template.name} ({template.department.value})")
        else:
            print("❌ Template do agente não encontrado")
        
        # Verificar ferramentas do agente
        tool_mappings = db.query(AgentToolMapping).filter(AgentToolMapping.agent_id == agent.id).all()
        print(f"\nFerramentas do agente ({len(tool_mappings)}):")
        
        for mapping in tool_mappings:
            tool = db.query(Tool).filter(Tool.id == mapping.tool_id).first()
            if tool:
                print(f"  - {tool.name} ({tool.type.value})")
                print(f"    Permissões: {json.dumps(mapping.permissions)}")
        
        # Verificar conversas do agente
        conversations = db.query(Conversation).filter(Conversation.agent_id == agent.id).all()
        print(f"\nConversas do agente ({len(conversations)}):")
        
        for conversation in conversations:
            print(f"  - {conversation.title} ({conversation.status.value})")
            
            # Verificar mensagens da conversa
            messages = db.query(Message).filter(Message.conversation_id == conversation.id).all()
            print(f"    Mensagens ({len(messages)}):")
            
            for message in messages:
                print(f"      - [{message.role.value}]: {message.content[:30]}...")
                
                # Verificar embedding da mensagem
                embedding = db.query(MessageEmbedding).filter(MessageEmbedding.message_id == message.id).first()
                if embedding:
                    print(f"        Embedding: Sim (dimensão: {len(embedding.embedding)})")
                
                # Verificar feedback da mensagem
                feedback = db.query(UserFeedback).filter(UserFeedback.message_id == message.id).first()
                if feedback:
                    print(f"        Feedback: {feedback.rating}/5 - '{feedback.feedback_text}'")
        
        # Verificar métricas do agente
        metrics = db.query(AgentMetrics).filter(AgentMetrics.agent_id == agent.id).all()
        print(f"\nMétricas do agente ({len(metrics)}):")
        
        for metric in metrics:
            print(f"  - Tempo de resposta: {metric.response_time}s")
            print(f"    Tokens utilizados: {metric.llm_tokens}")
            print(f"    Ferramentas usadas: {json.dumps(metric.tools_used)}")

def main():
    """Função principal que executa os testes."""
    print_separator("TESTE DE CONFIGURAÇÃO DO BANCO DE DADOS")
    print("Iniciando testes para verificar a configuração do banco de dados...")
    
    # Verificar se as tabelas foram criadas
    check_tables()
    
    # Verificar se a extensão pgvector está ativa
    check_vector_extension()
    
    # Inserir dados de teste
    insert_test_data()
    
    # Verificar relacionamentos
    check_relationships()
    
    print_separator("TESTES CONCLUÍDOS")

if __name__ == "__main__":
    main()