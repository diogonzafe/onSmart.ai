# app/tests/test_mcp.py
import os
import sys
import asyncio
import json
from typing import Dict, Any

# Configura path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Para ter uma sessão de DB para teste
from app.db.database import SessionLocal
from app.models.agent import Agent, AgentType
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.models.template import Template, TemplateDepartment
from app.core.mcp import get_mcp_formatter, get_mcp_processor

async def test_mcp_formatter():
    print("=== Testando Formatador MCP ===")
    
    # Obter formatter
    formatter = get_mcp_formatter()
    
    # Criar dados simulados para teste
    with SessionLocal() as db:
        # Buscar um agente existente para teste
        agent = db.query(Agent).first()
        
        if not agent:
            print("Nenhum agente encontrado para teste.")
            return False
        
        # Buscar uma conversa existente
        conversation = db.query(Conversation).filter(
            Conversation.agent_id == agent.id
        ).first()
        
        if not conversation:
            print("Nenhuma conversa encontrada para teste.")
            return False
        
        # Formatar o contexto
        context = formatter.format_conversation_context(
            db=db,
            agent=agent,
            conversation=conversation
        )
        
        # Mostrar resultado formatado
        print(f"Prompt do sistema: {context.get('messages', [])[0] if context.get('messages') else None}")
        print(f"Número de mensagens: {len(context.get('messages', []))}")
        print(f"Número de ferramentas: {len(context.get('tools', []))}")
        print(f"Memória: {json.dumps(context.get('memory', {}), indent=2)}")
        
        return True

async def test_mcp_processor():
    print("\n=== Testando Processador MCP ===")
    
    # Obter processor
    processor = get_mcp_processor()
    
    # Criar uma resposta de teste com ações
    test_response = """
    Vou ajudar você com isso. Primeiro, precisamos verificar os dados disponíveis.
    
    <action name="search_database">
    table=customers,
    query=status:active,
    limit=10
    </action>
    
    Depois de analisar os clientes ativos, podemos enviar um email informativo.
    
    {"action": "send_email", "params": {"to": "marketing@example.com", "subject": "Campanha", "template": "newsletter"}}
    
    Importante não compartilhar senhas ou dados sensíveis como tokens de api nesse processo.
    """
    
    # Processar a resposta
    result = processor.process_response(test_response)
    
    # Mostrar resultado
    print(f"Ações detectadas: {len(result['actions'])}")
    for i, action in enumerate(result['actions']):
        print(f"  Ação {i+1}: {action['name']}")
        print(f"    Parâmetros: {json.dumps(action['params'], indent=2)}")
    
    print(f"Avisos de validação: {len(result['validation']['warnings'])}")
    for warning in result['validation']['warnings']:
        print(f"  - {warning}")
    
    return True

async def run_all_tests():
    """Executa todos os testes MCP."""
    print("===== TESTES DO PROTOCOLO MCP =====\n")
    
    formatter_result = await test_mcp_formatter()
    processor_result = await test_mcp_processor()
    
    print("\n=== RESUMO DOS TESTES ===")
    print(f"Formatter: {'Passou' if formatter_result else 'Falhou'}")
    print(f"Processor: {'Passou' if processor_result else 'Falhou'}")

if __name__ == "__main__":
    asyncio.run(run_all_tests())