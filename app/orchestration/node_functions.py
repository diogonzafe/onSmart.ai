# app/orchestration/node_functions.py - Versão corrigida

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
    CORRIGIDO para sempre gerar uma resposta adequada.
    
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
    agent_service = get_agent_service(state.db_session)
    
    try:
        # Buscar agentes supervisor
        supervisor_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.SUPERVISOR,
            is_active=True
        )
        
        if not supervisor_agents:
            logger.error(f"Nenhum agente supervisor encontrado para usuário {state.user_id}")
            
            # CORREÇÃO: Gerar resposta explicativa em vez de apenas marcar como completo
            fallback_response = AgentResponse(
                agent_id="system_fallback",
                content=f"Não há agentes supervisor configurados para seu usuário. Para usar o sistema de orquestração multi-agentes, você precisa primeiro criar um agente do tipo 'Supervisor' que coordenará os outros agentes. Enquanto isso, posso tentar responder diretamente à sua pergunta: {state.current_message}",
                actions=[],
                confidence=0.3,
                metadata={"reason": "no_supervisor_agents", "suggestion": "create_supervisor_agent"}
            )
            
            # Adicionar resposta ao estado
            state.add_response(fallback_response)
            state.current_agent_id = "system_fallback"
            state.is_complete = True
            
            # Registrar tempo de processamento
            processing_time = time.time() - start_time
            state.processing_times["system_fallback"] = processing_time
            
            return state
        
        supervisor_agent = create_agent(
            agent_type=AgentType.SUPERVISOR,
            db=state.db_session,
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
        
    except Exception as e:
        logger.error(f"Erro no nó supervisor: {str(e)}")
        
        # CORREÇÃO: Gerar resposta de erro adequada
        error_response = AgentResponse(
            agent_id="system_error",
            content=f"Ocorreu um erro no processamento pelo agente supervisor: {str(e)}. Vou tentar responder diretamente: Para sua pergunta sobre '{state.current_message}', recomendo que entre em contato com nossa equipe de suporte para obter assistência personalizada.",
            actions=[],
            confidence=0.1,
            metadata={"error": str(e), "error_type": "supervisor_processing_error"}
        )
        
        # Adicionar resposta de erro ao estado
        state.add_response(error_response)
        state.current_agent_id = "system_error"
        state.is_complete = True
        
        # Registrar tempo de processamento
        processing_time = time.time() - start_time
        state.processing_times["system_error"] = processing_time
        
        return state

async def marketing_node(state: AgentState) -> AgentState:
    """
    Nó de marketing que processa mensagens relacionadas a marketing.
    CORRIGIDO para melhor tratamento de erros.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de marketing para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    try:
        # Obter instância do agente de marketing
        from app.services.agent_service import get_agent_service
        agent_service = get_agent_service(state.db_session)
        
        marketing_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.MARKETING,
            is_active=True
        )
        
        if not marketing_agents:
            logger.error(f"Nenhum agente de marketing encontrado para usuário {state.user_id}")
            
            # CORREÇÃO: Gerar resposta explicativa
            fallback_response = AgentResponse(
                agent_id="marketing_fallback",
                content=f"Não há agentes de marketing configurados. Para responder sua pergunta sobre marketing, recomendo que você crie um agente especializado em marketing. Enquanto isso, posso dar uma resposta geral: Para estratégias de marketing digital, é importante focar em análise de dados, segmentação de público e otimização de campanhas multi-canal.",
                actions=[],
                confidence=0.4,
                metadata={"reason": "no_marketing_agents", "suggestion": "create_marketing_agent"}
            )
            
            state.add_response(fallback_response)
            state.current_agent_id = "marketing_fallback"
            state.requires_fallback = True
            
            # Registrar tempo de processamento
            processing_time = time.time() - start_time
            state.processing_times["marketing_fallback"] = processing_time
            
            return state
        
        marketing_agent = create_agent(
            agent_type=AgentType.MARKETING,
            db=state.db_session,
            agent_record=marketing_agents[0]
        )
        
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
            confidence=0.9,
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
        
        # CORREÇÃO: Gerar resposta de erro específica para marketing
        error_response = AgentResponse(
            agent_id="marketing_error",
            content=f"Houve um problema ao processar sua solicitação de marketing. Como alternativa, posso sugerir: Para estratégias de marketing digital eficazes, considere focar em: 1) Análise de público-alvo, 2) Criação de conteúdo relevante, 3) Otimização de campanhas baseada em dados, 4) Integração multi-canal.",
            actions=[],
            confidence=0.3,
            metadata={"error": str(e), "error_type": "marketing_processing_error"}
        )
        
        state.add_response(error_response)
        state.current_agent_id = "marketing_error"
        state.requires_fallback = True
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    agent_id = state.current_agent_id or "marketing_unknown"
    state.processing_times[agent_id] = processing_time
    
    return state

async def sales_node(state: AgentState) -> AgentState:
    """
    Nó de vendas que processa mensagens relacionadas a vendas.
    CORRIGIDO para melhor tratamento de erros.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de vendas para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    try:
        # Obter instância do agente de vendas
        from app.services.agent_service import get_agent_service
        agent_service = get_agent_service(state.db_session)
        
        sales_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.SALES,
            is_active=True
        )
        
        if not sales_agents:
            logger.error(f"Nenhum agente de vendas encontrado para usuário {state.user_id}")
            
            # CORREÇÃO: Gerar resposta explicativa para vendas
            fallback_response = AgentResponse(
                agent_id="sales_fallback",
                content=f"Não há agentes de vendas configurados. Para sua pergunta sobre vendas, posso sugerir algumas práticas gerais: É importante focar na qualificação de leads, uso de CRM para acompanhar oportunidades, técnicas de fechamento adequadas e análise constante do funil de vendas para otimização de resultados.",
                actions=[],
                confidence=0.4,
                metadata={"reason": "no_sales_agents", "suggestion": "create_sales_agent"}
            )
            
            state.add_response(fallback_response)
            state.current_agent_id = "sales_fallback"
            state.requires_fallback = True
            
            # Registrar tempo de processamento
            processing_time = time.time() - start_time
            state.processing_times["sales_fallback"] = processing_time
            
            return state
        
        sales_agent = create_agent(
            agent_type=AgentType.SALES,
            db=state.db_session,
            agent_record=sales_agents[0]
        )
        
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
            confidence=0.9,
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
        
        # CORREÇÃO: Gerar resposta de erro específica para vendas
        error_response = AgentResponse(
            agent_id="sales_error",
            content=f"Houve um problema ao processar sua solicitação de vendas. Como alternativa, posso sugerir: Para otimizar vendas, considere: 1) Implementar um processo de qualificação de leads robusto, 2) Usar ferramentas de CRM para acompanhar oportunidades, 3) Treinar a equipe em técnicas de fechamento, 4) Analisar métricas de conversão regularmente.",
            actions=[],
            confidence=0.3,
            metadata={"error": str(e), "error_type": "sales_processing_error"}
        )
        
        state.add_response(error_response)
        state.current_agent_id = "sales_error"
        state.requires_fallback = True
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    agent_id = state.current_agent_id or "sales_unknown"
    state.processing_times[agent_id] = processing_time
    
    return state

async def finance_node(state: AgentState) -> AgentState:
    """
    Nó de finanças que processa mensagens relacionadas a finanças.
    CORRIGIDO para melhor tratamento de erros.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de finanças para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    try:
        # Obter instância do agente de finanças
        from app.services.agent_service import get_agent_service
        agent_service = get_agent_service(state.db_session)
        
        finance_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.FINANCE,
            is_active=True
        )
        
        if not finance_agents:
            logger.error(f"Nenhum agente de finanças encontrado para usuário {state.user_id}")
            
            # CORREÇÃO: Gerar resposta explicativa para finanças
            fallback_response = AgentResponse(
                agent_id="finance_fallback",
                content=f"Não há agentes financeiros configurados. Para sua pergunta sobre finanças, posso oferecer algumas diretrizes gerais: É importante manter controle rigoroso do fluxo de caixa, acompanhar indicadores financeiros como ROI e margem de lucro, fazer análise de viabilidade de investimentos e manter relatórios financeiros atualizados para tomada de decisões.",
                actions=[],
                confidence=0.4,
                metadata={"reason": "no_finance_agents", "suggestion": "create_finance_agent"}
            )
            
            state.add_response(fallback_response)
            state.current_agent_id = "finance_fallback"
            state.requires_fallback = True
            
            # Registrar tempo de processamento
            processing_time = time.time() - start_time
            state.processing_times["finance_fallback"] = processing_time
            
            return state
        
        finance_agent = create_agent(
            agent_type=AgentType.FINANCE,
            db=state.db_session,
            agent_record=finance_agents[0]
        )
        
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
            confidence=0.9,
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
        
        # CORREÇÃO: Gerar resposta de erro específica para finanças
        error_response = AgentResponse(
            agent_id="finance_error",
            content=f"Houve um problema ao processar sua solicitação financeira. Como alternativa, posso sugerir: Para uma gestão financeira eficaz, considere: 1) Implementar controles rigorosos de fluxo de caixa, 2) Acompanhar KPIs financeiros regularmente, 3) Fazer análises de viabilidade antes de investimentos, 4) Manter relatórios financeiros atualizados para decisões estratégicas.",
            actions=[],
            confidence=0.3,
            metadata={"error": str(e), "error_type": "finance_processing_error"}
        )
        
        state.add_response(error_response)
        state.current_agent_id = "finance_error"
        state.requires_fallback = True
    
    # Registrar tempo de processamento
    processing_time = time.time() - start_time
    agent_id = state.current_agent_id or "finance_unknown"
    state.processing_times[agent_id] = processing_time
    
    return state

async def fallback_node(state: AgentState) -> AgentState:
    """
    Nó de fallback para quando os agentes especializados falham.
    MELHORADO para dar respostas mais úteis.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Estado atualizado após processamento
    """
    logger.info(f"Executando nó de fallback para conversa {state.conversation_id}")
    
    # Registrar início do processamento
    start_time = time.time()
    
    # Analisar a mensagem original para dar uma resposta mais contextual
    message = state.current_message.lower()
    
    # CORREÇÃO: Respostas mais específicas baseadas no conteúdo
    if any(keyword in message for keyword in ["marketing", "campanha", "publicidade", "social", "mídia"]):
        fallback_content = """Como não há agentes de marketing configurados, posso oferecer algumas orientações gerais:

**Estratégia de Marketing Digital:**
• Defina seu público-alvo e personas
• Crie conteúdo relevante e engajador
• Use análise de dados para otimizar campanhas
• Integre múltiplos canais (social media, email, SEO)
• Acompanhe métricas como CTR, conversão e ROI

Para uma análise mais detalhada, configure um agente de marketing especializado."""

    elif any(keyword in message for keyword in ["vendas", "venda", "cliente", "negociação", "proposta"]):
        fallback_content = """Como não há agentes de vendas configurados, posso compartilhar algumas práticas essenciais:

**Processo de Vendas Eficaz:**
• Qualifique leads adequadamente (BANT: Budget, Authority, Need, Timeline)
• Use CRM para acompanhar oportunidades
• Desenvolva técnicas de discovery para entender necessidades
• Prepare propostas personalizadas e convincentes
• Implemente processo de follow-up estruturado

Para estratégias mais específicas, considere criar um agente de vendas especializado."""

    elif any(keyword in message for keyword in ["financeiro", "finanças", "orçamento", "lucro", "receita", "custo"]):
        fallback_content = """Como não há agentes financeiros configurados, posso orientar sobre princípios fundamentais:

**Gestão Financeira Estratégica:**
• Mantenha controle rigoroso do fluxo de caixa
• Acompanhe indicadores como ROI, margem de lucro e ponto de equilíbrio
• Realize análises de viabilidade antes de investimentos
• Mantenha relatórios financeiros atualizados
• Implemente controles internos e auditoria regular

Para análises mais profundas, recomendo configurar um agente financeiro especializado."""

    else:
        fallback_content = f"""Recebi sua solicitação: "{state.current_message}"

Para fornecer uma resposta mais precisa e especializada, recomendo que você configure agentes específicos para cada área:

• **Agente Supervisor**: Para coordenar múltiplos departamentos
• **Agente de Marketing**: Para estratégias de comunicação e campanhas
• **Agente de Vendas**: Para processos comerciais e negociação
• **Agente Financeiro**: Para análises e controle financeiro

Enquanto isso, posso tentar responder de forma geral. Por favor, reformule sua pergunta se precisar de orientações específicas."""
    
    # Criar resposta de fallback melhorada
    agent_id = "fallback_system"
    
    fallback_response = AgentResponse(
        agent_id=agent_id,
        content=fallback_content,
        actions=[],
        confidence=0.6,
        metadata={
            "fallback": True,
            "reason": "no_specialized_agents",
            "suggestion": "configure_agents",
            "analyzed_keywords": [word for word in ["marketing", "vendas", "financeiro"] if word in message]
        }
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