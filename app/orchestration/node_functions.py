from typing import Dict, List, Any, Optional
import logging
import time
from datetime import datetime

from app.orchestration.state_manager import AgentState, AgentResponse, AgentAction
from app.agents import create_agent
from app.models.agent import AgentType

logger = logging.getLogger(__name__)

async def supervisor_node(state: AgentState) -> AgentState:
    """
    Nó do supervisor que coordena o fluxo de trabalho.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó supervisor para conversa {state.conversation_id}")
    
    # Verificar se o fluxo já foi concluído
    if state.is_complete:
        logger.info("Fluxo já concluído, retornando estado atual")
        return state
    
    # Registrar início do processamento
    start_time = time.time()
    
    # Obter instância do agente supervisor
    from app.services.agent_service import get_agent_service
    agent_service = get_agent_service(None)  # Será substituído pelo db_session na chamada real
    
    # Modificado para criar uma lista diretamente
    # Os testes funcionam sem await porque usam um mock que já retorna uma lista
    supervisor_agents = await agent_service.list_agents(
        user_id=state.user_id,
        agent_type=AgentType.SUPERVISOR,
        is_active=True
    )
    
    if not supervisor_agents:
        logger.error(f"Nenhum agente supervisor encontrado para usuário {state.user_id}")
        state.is_complete = True
        return state
    
    supervisor_agent = create_agent(
        agent_type=AgentType.SUPERVISOR,
        db=None,  # Será substituído na chamada real
        agent_record=supervisor_agents[0]
    )
    
    # Processar a mensagem com o supervisor
    response = await supervisor_agent.process_message(
        conversation_id=state.conversation_id,
        message=state.current_message
    )
    
    # Extrair metadados relevantes da resposta
    selected_dept = response.get("metadata", {}).get("selected_department")
    
    # Criar resposta do agente usando a classe AgentResponse
    agent_response = AgentResponse(
        agent_id=supervisor_agents[0].id,
        content=response["message"]["content"],
        actions=[
            AgentAction(
                name="route_to_department",
                params={"department": selected_dept},
                agent_id=supervisor_agents[0].id
            )
        ],
        metadata=response.get("metadata", {})
    )
    
    # Atualizar o estado
    state.add_response(agent_response)
    state.previous_agent_id = state.current_agent_id
    state.current_agent_id = supervisor_agents[0].id
    
    # Se o supervisor não identificou um departamento, concluir o fluxo
    if not selected_dept:
        state.is_complete = True
    else:
        state.next_agent_id = selected_dept
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    state.processing_times[supervisor_agents[0].id] = processing_time
    
    return state

async def marketing_node(state: AgentState) -> AgentState:
    """
    Nó de marketing que processa mensagens relacionadas a marketing.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de marketing para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    # Obter instância do agente de marketing
    from app.services.agent_service import get_agent_service
    agent_service = get_agent_service(None)  # Será substituído pelo db_session na chamada real
    
    # Adicionar await aqui
    marketing_agents = await agent_service.list_agents(
        user_id=state.user_id,
        agent_type=AgentType.MARKETING,
        is_active=True
    )
    
    if not marketing_agents:
        logger.error(f"Nenhum agente de marketing encontrado para usuário {state.user_id}")
        state.requires_fallback = True
        return state
    
    marketing_agent = create_agent(
        agent_type=AgentType.MARKETING,
        db=None,  # Será substituído na chamada real
        agent_record=marketing_agents[0]
    )
    
    try:
        # Processar a mensagem com o agente de marketing
        response = await marketing_agent.process_message(
            conversation_id=state.conversation_id,
            message=state.current_message
        )
        
        # Criar resposta do agente usando AgentResponse
        agent_response = AgentResponse(
            agent_id=marketing_agents[0].id,
            content=response["message"]["content"],
            actions=[
                AgentAction(
                    name=action.get("name", "unknown"),
                    params=action.get("params", {}),
                    agent_id=marketing_agents[0].id
                )
                for action in response.get("actions", [])
            ],
            confidence=0.9,  # Valor exemplo, poderia ser calculado
            metadata=response.get("metadata", {})
        )
        
        # Atualizar o estado
        state.add_response(agent_response)
        state.previous_agent_id = state.current_agent_id
        state.current_agent_id = marketing_agents[0].id
        
        # Incrementar a tentativa
        state.attempt_count += 1
        
        # Se atingiu o máximo de tentativas, concluir o fluxo
        if state.attempt_count >= state.max_attempts:
            state.is_complete = True
            
    except Exception as e:
        logger.error(f"Erro ao processar mensagem com agente de marketing: {str(e)}")
        state.requires_fallback = True
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    state.processing_times[marketing_agents[0].id] = processing_time
    
    return state

# Adicionar em app/orchestration/node_functions.py

async def sales_node(state: AgentState) -> AgentState:
    """
    Nó de vendas que processa mensagens relacionadas a vendas.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de vendas para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    # Obter instância do agente de vendas
    from app.services.agent_service import get_agent_service
    agent_service = get_agent_service(None)  # Será substituído pelo db_session na chamada real
    
    sales_agents = await agent_service.list_agents(
        user_id=state.user_id,
        agent_type=AgentType.SALES,
        is_active=True
    )
    
    if not sales_agents:
        logger.error(f"Nenhum agente de vendas encontrado para usuário {state.user_id}")
        state.requires_fallback = True
        return state
    
    sales_agent = create_agent(
        agent_type=AgentType.SALES,
        db=None,  # Será substituído na chamada real
        agent_record=sales_agents[0]
    )
    
    try:
        # Processar a mensagem com o agente de vendas
        response = await sales_agent.process_message(
            conversation_id=state.conversation_id,
            message=state.current_message
        )
        
        # Criar resposta do agente usando AgentResponse
        agent_response = AgentResponse(
            agent_id=sales_agents[0].id,
            content=response["message"]["content"],
            actions=[
                AgentAction(
                    name=action.get("name", "unknown"),
                    params=action.get("params", {}),
                    agent_id=sales_agents[0].id
                )
                for action in response.get("actions", [])
            ],
            confidence=0.9,  # Valor exemplo, poderia ser calculado
            metadata=response.get("metadata", {})
        )
        
        # Atualizar o estado
        state.add_response(agent_response)
        state.previous_agent_id = state.current_agent_id
        state.current_agent_id = sales_agents[0].id
        
        # Incrementar a tentativa
        state.attempt_count += 1
        
        # Se atingiu o máximo de tentativas, concluir o fluxo
        if state.attempt_count >= state.max_attempts:
            state.is_complete = True
            
    except Exception as e:
        logger.error(f"Erro ao processar mensagem com agente de vendas: {str(e)}")
        state.requires_fallback = True
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    state.processing_times[sales_agents[0].id] = processing_time
    
    return state

async def finance_node(state: AgentState) -> AgentState:
    """
    Nó de finanças que processa mensagens relacionadas a finanças.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de finanças para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    # Obter instância do agente de finanças
    from app.services.agent_service import get_agent_service
    agent_service = get_agent_service(None)  # Será substituído pelo db_session na chamada real
    
    finance_agents = await agent_service.list_agents(
        user_id=state.user_id,
        agent_type=AgentType.FINANCE,
        is_active=True
    )
    
    if not finance_agents:
        logger.error(f"Nenhum agente de finanças encontrado para usuário {state.user_id}")
        state.requires_fallback = True
        return state
    
    finance_agent = create_agent(
        agent_type=AgentType.FINANCE,
        db=None,  # Será substituído na chamada real
        agent_record=finance_agents[0]
    )
    
    try:
        # Processar a mensagem com o agente de finanças
        response = await finance_agent.process_message(
            conversation_id=state.conversation_id,
            message=state.current_message
        )
        
        # Criar resposta do agente usando AgentResponse
        agent_response = AgentResponse(
            agent_id=finance_agents[0].id,
            content=response["message"]["content"],
            actions=[
                AgentAction(
                    name=action.get("name", "unknown"),
                    params=action.get("params", {}),
                    agent_id=finance_agents[0].id
                )
                for action in response.get("actions", [])
            ],
            confidence=0.9,  # Valor exemplo, poderia ser calculado
            metadata=response.get("metadata", {})
        )
        
        # Atualizar o estado
        state.add_response(agent_response)
        state.previous_agent_id = state.current_agent_id
        state.current_agent_id = finance_agents[0].id
        
        # Incrementar a tentativa
        state.attempt_count += 1
        
        # Se atingiu o máximo de tentativas, concluir o fluxo
        if state.attempt_count >= state.max_attempts:
            state.is_complete = True
            
    except Exception as e:
        logger.error(f"Erro ao processar mensagem com agente de finanças: {str(e)}")
        state.requires_fallback = True
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    state.processing_times[finance_agents[0].id] = processing_time
    
    return state

async def fallback_node(state: AgentState) -> AgentState:
    """
    Nó de fallback para quando os agentes especializados falham.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de fallback para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    # Criar resposta de fallback
    agent_id = "fallback_system"
    
    # Usar a classe AgentResponse em vez de um dicionário
    fallback_response = AgentResponse(
        agent_id=agent_id,
        content="Não foi possível processar sua solicitação com nossos agentes especializados. " +
                "Por favor, tente reformular sua pergunta ou entre em contato com nosso suporte.",
        actions=[],
        confidence=0.5,
        metadata={"fallback": True}
    )
    
    # Atualizar o estado
    state.add_response(fallback_response)
    state.previous_agent_id = state.current_agent_id
    state.current_agent_id = agent_id
    
    # Marcar como concluído após fallback
    state.is_complete = True
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    state.processing_times[agent_id] = processing_time
    
    return state