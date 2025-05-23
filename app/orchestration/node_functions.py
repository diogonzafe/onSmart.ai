# Substitua o conteúdo completo do arquivo app/orchestration/node_functions.py por este código corrigido:

from typing import Dict, List, Any, Optional
import logging
import time
from datetime import datetime

from app.orchestration.state_manager import AgentState, AgentResponse, AgentAction
from app.models.agent import AgentType

# CORREÇÃO: Importações internas para evitar circular imports
def get_agent_service(db_session):
    """Import interno para evitar circular imports."""
    from app.services.agent_service import get_agent_service as _get_agent_service
    return _get_agent_service(db_session)

def create_agent(agent_type, db, agent_record):
    """Import interno para evitar circular imports."""
    from app.agents import create_agent as _create_agent
    return _create_agent(agent_type, db, agent_record)

logger = logging.getLogger(__name__)

def _analyze_message_for_department(message: str) -> str:
    """
    Analisa a mensagem para determinar qual departamento é mais adequado.
    COMPLETAMENTE REESCRITA com algoritmo mais eficaz.
    
    Args:
        message: Mensagem do usuário
        
    Returns:
        Departamento mais adequado ('marketing', 'sales', 'finance')
    """
    import re
    
    # Converter para lowercase para análise
    message_lower = message.lower()
    
    # Palavras-chave organizadas por peso e relevância
    department_keywords = {
        "marketing": {
            "high_weight": [
                'marketing', 'campanha', 'publicidade', 'propaganda', 'comunicação',
                'mídia', 'social', 'redes sociais', 'conteúdo', 'branding', 'marca',
                'engajamento', 'alcance', 'seo', 'blog', 'newsletter', 'influencer'
            ],
            "medium_weight": [
                'adwords', 'facebook', 'instagram', 'linkedin', 'youtube', 'tiktok',
                'viral', 'hashtag', 'post', 'stories', 'feed', 'perfil', 'seguidores',
                'likes', 'shares', 'impressões', 'cliques', 'artigo'
            ],
            "contextual_patterns": [
                r'estratégia.{0,15}(digital|online|comunicação|marca|conteúdo)',
                r'análise.{0,15}(mercado|concorrência|mídia|engajamento)',
                r'gestão.{0,15}(marca|comunidade|reputação)'
            ]
        },
        
        "sales": {
            "high_weight": [
                'vendas', 'venda', 'vender', 'cliente', 'lead', 'prospect', 'prospects',
                'prospecção', 'pipeline', 'funil', 'conversão', 'oportunidade',
                'negociação', 'proposta', 'qualificar', 'qualificação', 'comercial'
            ],
            "medium_weight": [
                'orçamento', 'cotação', 'desconto', 'comissão', 'meta', 'quota',
                'crm', 'follow-up', 'demo', 'trial', 'fechamento', 'upsell',
                'cross-sell', 'relacionamento', 'account', 'b2b', 'b2c'
            ],
            "contextual_patterns": [
                r'processo.{0,15}(venda|comercial|negociação|fechamento)',
                r'estratégia.{0,15}(vendas|comercial|cliente)',
                r'gestão.{0,15}(cliente|relacionamento|pipeline)',
                r'como.{0,15}(vender|converter|fechar|qualificar)'
            ]
        },
        
        "finance": {
            "high_weight": [
                'financeiro', 'finanças', 'contábil', 'contabilidade', 'orçamento',
                'budget', 'custo', 'despesa', 'receita', 'faturamento', 'fluxo',
                'caixa', 'roi', 'margem', 'lucro', 'investimento'
            ],
            "medium_weight": [
                'cobrança', 'pagamento', 'cash', 'flow', 'dre', 'demonstrativo',
                'balanço', 'balancete', 'prejuízo', 'ebitda', 'viabilidade',
                'indicador', 'kpi', 'métrica', 'controle', 'auditoria', 'fiscal'
            ],
            "contextual_patterns": [
                r'análise.{0,15}(financeira|econômica|custo|viabilidade)',
                r'controle.{0,15}(interno|gestão|orçamentário|financeiro)',
                r'relatório.{0,15}(financeiro|gerencial|contábil)',
                r'fluxo.{0,10}de.{0,10}caixa',
                r'como.{0,15}calcular.{0,15}(roi|margem|lucro)'
            ]
        }
    }
    
    # Calcular scores
    scores = {"marketing": 0, "sales": 0, "finance": 0}
    
    for dept, keywords_data in department_keywords.items():
        # Palavras de alto peso (3 pontos cada)
        for keyword in keywords_data["high_weight"]:
            if keyword in message_lower:
                scores[dept] += 3
                logger.debug(f"High weight match '{keyword}' para {dept}")
        
        # Palavras de peso médio (2 pontos cada)
        for keyword in keywords_data["medium_weight"]:
            if keyword in message_lower:
                scores[dept] += 2
                logger.debug(f"Medium weight match '{keyword}' para {dept}")
        
        # Padrões contextuais (2 pontos cada)
        for pattern in keywords_data["contextual_patterns"]:
            if re.search(pattern, message_lower):
                scores[dept] += 2
                logger.debug(f"Contextual pattern match para {dept}")
    
    # Log dos scores
    logger.debug(f"Scores finais - Marketing: {scores['marketing']}, Sales: {scores['sales']}, Finance: {scores['finance']}")
    
    # Determinar vencedor
    max_score = max(scores.values())
    
    if max_score > 0:
        # Retornar departamento com maior score
        for dept, score in scores.items():
            if score == max_score:
                logger.info(f"Departamento identificado: {dept} (score: {score})")
                return dept
    
    # Fallbacks específicos para casos sem matches
    if len(message.split()) < 3:
        # Mensagens muito curtas
        logger.info("Mensagem muito curta - fallback para marketing")
        return "marketing"
    
    # Análise de palavras comuns como fallback
    common_sales_words = ["comprar", "preço", "valor", "pagar", "cliente"]
    common_finance_words = ["dinheiro", "gasto", "economia", "caro"]
    
    if any(word in message_lower for word in common_sales_words):
        logger.info("Palavras comuns de vendas detectadas - fallback para sales")
        return "sales"
    elif any(word in message_lower for word in common_finance_words):
        logger.info("Palavras comuns financeiras detectadas - fallback para finance")
        return "finance"
    
    # Default final
    logger.info("Nenhum padrão específico identificado - fallback para marketing")
    return "marketing"


async def supervisor_node(state: AgentState) -> AgentState:
    """
    Nó do supervisor que coordena o fluxo de trabalho.
    CORRIGIDO para funcionar sem agente supervisor, fazendo roteamento inteligente.
    """
    logger.info(f"Executando nó supervisor para conversa {state.conversation_id}")
    
    if state.is_complete:
        logger.info("Fluxo já concluído, retornando estado atual")
        return state
    
    start_time = time.time()
    
    try:
        # Obter instância do agente supervisor usando import interno
        agent_service = get_agent_service(state.db_session)
        
        # Buscar agentes supervisor
        supervisor_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.SUPERVISOR,
            is_active=True
        )
        
        if supervisor_agents:
            # FLUXO COM SUPERVISOR
            logger.info(f"Usando agente supervisor: {supervisor_agents[0].id}")
            
            supervisor_agent = create_agent(
                agent_type=AgentType.SUPERVISOR,
                db=state.db_session,
                agent_record=supervisor_agents[0]
            )
            
            response = await supervisor_agent.process_message(
                conversation_id=state.conversation_id,
                message=state.current_message
            )
            
            selected_dept = response.get("metadata", {}).get("selected_department")
            
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
            
            state.add_response(agent_response)
            state.previous_agent_id = state.current_agent_id
            state.current_agent_id = supervisor_agents[0].id
            
            if not selected_dept:
                state.is_complete = True
            else:
                state.next_agent_id = selected_dept
        
        else:
            # FLUXO SEM SUPERVISOR: Roteamento inteligente automático
            logger.info("Roteamento inteligente automático ativado")
            
            department = _analyze_message_for_department(state.current_message)
            logger.info(f"Departamento identificado: {department}")
            
            # Verificar agentes disponíveis para o departamento
            dept_type_map = {
                "marketing": AgentType.MARKETING,
                "sales": AgentType.SALES,
                "finance": AgentType.FINANCE
            }
            
            department_agents = []
            if department in dept_type_map:
                department_agents = await agent_service.list_agents(
                    user_id=state.user_id,
                    agent_type=dept_type_map[department],
                    is_active=True
                )
            
            if department_agents:
                # Agente especializado disponível
                auto_response = AgentResponse(
                    agent_id="auto_supervisor",
                    content=f"Identifiquei que sua solicitação sobre '{state.current_message[:80]}...' está relacionada a **{department}**. Vou encaminhar para o agente especializado.",
                    actions=[
                        AgentAction(
                            name="route_to_department",
                            params={"department": department},
                            agent_id="auto_supervisor"
                        )
                    ],
                    confidence=0.8,
                    metadata={
                        "selected_department": department,
                        "routing_method": "automatic_analysis",
                        "agent_available": True
                    }
                )
                
                state.add_response(auto_response)
                state.current_agent_id = "auto_supervisor"
                state.next_agent_id = department
                
                logger.info(f"Roteamento para {department} realizado com sucesso")
            
            else:
                # Buscar qualquer agente como fallback
                all_agents = []
                for agent_type in [AgentType.MARKETING, AgentType.SALES, AgentType.FINANCE]:
                    agents = await agent_service.list_agents(
                        user_id=state.user_id,
                        agent_type=agent_type,
                        is_active=True
                    )
                    all_agents.extend(agents)
                
                if all_agents:
                    # Usar primeiro agente disponível
                    fallback_agent = all_agents[0]
                    fallback_dept = fallback_agent.type.value
                    
                    fallback_response = AgentResponse(
                        agent_id="auto_supervisor_fallback",
                        content=f"Não encontrei um agente especializado em **{department}**, mas tenho um agente de **{fallback_dept}** que pode ajudar. Vou encaminhar sua solicitação.",
                        actions=[
                            AgentAction(
                                name="route_to_department",
                                params={"department": fallback_dept},
                                agent_id="auto_supervisor_fallback"
                            )
                        ],
                        confidence=0.6,
                        metadata={
                            "selected_department": fallback_dept,
                            "routing_method": "fallback_to_available",
                            "original_intent": department
                        }
                    )
                    
                    state.add_response(fallback_response)
                    state.current_agent_id = "auto_supervisor_fallback"
                    state.next_agent_id = fallback_dept
                
                else:
                    # Nenhum agente disponível - resposta educativa
                    no_agents_response = AgentResponse(
                        agent_id="system_guidance",
                        content=f"""Para sua pergunta sobre **{state.current_message[:100]}{'...' if len(state.current_message) > 100 else ''}**, posso oferecer orientações gerais:

{_generate_general_response(state.current_message, department)}

**💡 Recomendação:** Configure agentes especializados para respostas mais precisas:
• 🤖 **Agente de Marketing** - Estratégias de comunicação e campanhas
• 💼 **Agente de Vendas** - Processos comerciais e gestão de clientes  
• 💰 **Agente Financeiro** - Análises financeiras e controle de custos""",
                        actions=[],
                        confidence=0.4,
                        metadata={
                            "reason": "no_agents_configured",
                            "suggested_department": department,
                            "suggestion": "create_specialized_agents"
                        }
                    )
                    
                    state.add_response(no_agents_response)
                    state.current_agent_id = "system_guidance"
                    state.is_complete = True
        
        # Registrar tempo de processamento
        processing_time = time.time() - start_time
        agent_id = state.current_agent_id or "supervisor_unknown"
        state.processing_times[agent_id] = processing_time
        
        return state
        
    except Exception as e:
        logger.error(f"Erro no nó supervisor: {str(e)}")
        
        error_response = AgentResponse(
            agent_id="system_error",
            content=f"""Ocorreu um erro no processamento: {str(e)}

Como alternativa, aqui estão algumas orientações gerais:

{_generate_general_response(state.current_message, "geral")}""",
            actions=[],
            confidence=0.1,
            metadata={"error": str(e), "error_type": "supervisor_processing_error"}
        )
        
        state.add_response(error_response)
        state.current_agent_id = "system_error"
        state.is_complete = True
        
        processing_time = time.time() - start_time
        state.processing_times["system_error"] = processing_time
        
        return state


def _generate_general_response(message: str, department: str) -> str:
    """Gera resposta geral contextualizada."""
    responses = {
        "marketing": """**📱 Marketing Digital - Diretrizes Gerais:**
• Defina público-alvo e personas claramente
• Crie conteúdo relevante e engajador
• Use análise de dados para otimizar campanhas
• Integre múltiplos canais (social, email, SEO)
• Monitore métricas como reach, engagement e ROI""",

        "sales": """**💼 Estratégia de Vendas - Práticas Essenciais:**
• Implemente processo estruturado de qualificação
• Use CRM para acompanhar oportunidades
• Desenvolva técnicas de discovery e fechamento
• Mantenha follow-up consistente
• Monitore métricas de conversão e ciclo de vendas""",

        "finance": """**💰 Gestão Financeira - Fundamentos:**
• Mantenha controle rigoroso do fluxo de caixa
• Acompanhe indicadores como ROI e margem
• Realize análises de viabilidade antes de investir
• Implemente controles internos eficazes
• Gere relatórios regulares para tomada de decisão""",

        "geral": """**🎯 Orientações Integradas:**
• **Marketing:** Foque em estratégias data-driven
• **Vendas:** Desenvolva processos estruturados
• **Finanças:** Monitore indicadores de performance
• **Integração:** Alinhe todos os departamentos para máxima eficiência"""
    }
    
    return responses.get(department, responses["geral"])


# Implementar as outras funções de nó (marketing, sales, finance, fallback)
async def marketing_node(state: AgentState) -> AgentState:
    """Nó de marketing."""
    logger.info(f"Executando nó de marketing para conversa {state.conversation_id}")
    
    start_time = time.time()
    
    try:
        agent_service = get_agent_service(state.db_session)
        
        marketing_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.MARKETING,
            is_active=True
        )
        
        if not marketing_agents:
            fallback_response = AgentResponse(
                agent_id="marketing_fallback",
                content="Não há agentes de marketing configurados. Para estratégias de marketing digital, recomendo: 1) Definir público-alvo, 2) Criar conteúdo relevante, 3) Usar análise de dados, 4) Integrar múltiplos canais.",
                actions=[],
                confidence=0.4,
                metadata={"reason": "no_marketing_agents"}
            )
            
            state.add_response(fallback_response)
            state.current_agent_id = "marketing_fallback"
            state.requires_fallback = True
        else:
            marketing_agent = create_agent(
                agent_type=AgentType.MARKETING,
                db=state.db_session,
                agent_record=marketing_agents[0]
            )
            
            response = await marketing_agent.process_message(
                conversation_id=state.conversation_id,
                message=state.current_message
            )
            
            agent_response = AgentResponse(
                agent_id=marketing_agents[0].id,
                content=response["message"]["content"],
                actions=[],
                confidence=0.9,
                metadata=response.get("metadata", {})
            )
            
            state.add_response(agent_response)
            state.current_agent_id = marketing_agents[0].id
        
        state.attempt_count += 1
        if state.attempt_count >= state.max_attempts:
            state.is_complete = True
            
    except Exception as e:
        logger.error(f"Erro no nó de marketing: {str(e)}")
        
        error_response = AgentResponse(
            agent_id="marketing_error",
            content=f"Erro no processamento de marketing. Orientação geral: Foque em análise de público-alvo, criação de conteúdo relevante e otimização baseada em dados.",
            actions=[],
            confidence=0.3,
            metadata={"error": str(e)}
        )
        
        state.add_response(error_response)
        state.current_agent_id = "marketing_error"
        state.requires_fallback = True
    
    processing_time = time.time() - start_time
    agent_id = state.current_agent_id or "marketing_unknown"
    state.processing_times[agent_id] = processing_time
    
    return state


async def sales_node(state: AgentState) -> AgentState:
    """Nó de vendas."""
    logger.info(f"Executando nó de vendas para conversa {state.conversation_id}")
    
    start_time = time.time()
    
    try:
        agent_service = get_agent_service(state.db_session)
        
        sales_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.SALES,
            is_active=True
        )
        
        if not sales_agents:
            fallback_response = AgentResponse(
                agent_id="sales_fallback",
                content="Não há agentes de vendas configurados. Para otimizar vendas: 1) Qualifique leads adequadamente, 2) Use CRM, 3) Desenvolva técnicas de fechamento, 4) Mantenha follow-up consistente.",
                actions=[],
                confidence=0.4,
                metadata={"reason": "no_sales_agents"}
            )
            
            state.add_response(fallback_response)
            state.current_agent_id = "sales_fallback"
            state.requires_fallback = True
        else:
            sales_agent = create_agent(
                agent_type=AgentType.SALES,
                db=state.db_session,
                agent_record=sales_agents[0]
            )
            
            response = await sales_agent.process_message(
                conversation_id=state.conversation_id,
                message=state.current_message
            )
            
            agent_response = AgentResponse(
                agent_id=sales_agents[0].id,
                content=response["message"]["content"],
                actions=[],
                confidence=0.9,
                metadata=response.get("metadata", {})
            )
            
            state.add_response(agent_response)
            state.current_agent_id = sales_agents[0].id
        
        state.attempt_count += 1
        if state.attempt_count >= state.max_attempts:
            state.is_complete = True
            
    except Exception as e:
        logger.error(f"Erro no nó de vendas: {str(e)}")
        
        error_response = AgentResponse(
            agent_id="sales_error",
            content=f"Erro no processamento de vendas. Orientação geral: Implemente qualificação de leads, use CRM para acompanhar oportunidades e desenvolva técnicas de fechamento.",
            actions=[],
            confidence=0.3,
            metadata={"error": str(e)}
        )
        
        state.add_response(error_response)
        state.current_agent_id = "sales_error"  
        state.requires_fallback = True
    
    processing_time = time.time() - start_time
    agent_id = state.current_agent_id or "sales_unknown"
    state.processing_times[agent_id] = processing_time
    
    return state


async def finance_node(state: AgentState) -> AgentState:
    """Nó de finanças."""
    logger.info(f"Executando nó de finanças para conversa {state.conversation_id}")
    
    start_time = time.time()
    
    try:
        agent_service = get_agent_service(state.db_session)
        
        finance_agents = await agent_service.list_agents(
            user_id=state.user_id,
            agent_type=AgentType.FINANCE,
            is_active=True
        )
        
        if not finance_agents:
            fallback_response = AgentResponse(
                agent_id="finance_fallback",
                content="Não há agentes financeiros configurados. Para gestão financeira eficaz: 1) Controle fluxo de caixa, 2) Monitore indicadores como ROI, 3) Faça análises de viabilidade, 4) Mantenha relatórios atualizados.",
                actions=[],
                confidence=0.4,
                metadata={"reason": "no_finance_agents"}
            )
            
            state.add_response(fallback_response)
            state.current_agent_id = "finance_fallback"
            state.requires_fallback = True
        else:
            finance_agent = create_agent(
                agent_type=AgentType.FINANCE,
                db=state.db_session,
                agent_record=finance_agents[0]
            )
            
            response = await finance_agent.process_message(
                conversation_id=state.conversation_id,
                message=state.current_message
            )
            
            agent_response = AgentResponse(
                agent_id=finance_agents[0].id,
                content=response["message"]["content"],
                actions=[],
                confidence=0.9,
                metadata=response.get("metadata", {})
            )
            
            state.add_response(agent_response)
            state.current_agent_id = finance_agents[0].id
        
        state.attempt_count += 1
        if state.attempt_count >= state.max_attempts:
            state.is_complete = True
            
    except Exception as e:
        logger.error(f"Erro no nó de finanças: {str(e)}")
        
        error_response = AgentResponse(
            agent_id="finance_error",
            content=f"Erro no processamento financeiro. Orientação geral: Mantenha controle de fluxo de caixa, acompanhe indicadores financeiros e realize análises de viabilidade regularmente.",
            actions=[],
            confidence=0.3,
            metadata={"error": str(e)}
        )
        
        state.add_response(error_response)
        state.current_agent_id = "finance_error"
        state.requires_fallback = True
    
    processing_time = time.time() - start_time
    agent_id = state.current_agent_id or "finance_unknown"
    state.processing_times[agent_id] = processing_time
    
    return state


async def fallback_node(state: AgentState) -> AgentState:
    """Nó de fallback para casos não tratados."""
    logger.info(f"Executando nó de fallback para conversa {state.conversation_id}")
    
    start_time = time.time()
    
    message = state.current_message.lower()
    
    # Resposta contextualizada baseada na análise da mensagem
    if any(keyword in message for keyword in ["marketing", "campanha", "social"]):
        fallback_content = """**📱 Orientações para Marketing:**
• Defina personas e público-alvo específicos
• Crie conteúdo relevante e engajador
• Use análise de dados para otimizar campanhas
• Integre múltiplos canais (social, email, SEO)
• Monitore métricas como reach, engagement e ROI"""
    
    elif any(keyword in message for keyword in ["vendas", "cliente", "negociação"]):
        fallback_content = """**💼 Orientações para Vendas:**
• Implemente processo de qualificação de leads
• Use CRM para gestão de oportunidades
• Desenvolva técnicas de discovery e fechamento
• Mantenha follow-up consistente com prospects
• Monitore métricas de conversão e ciclo de vendas"""
    
    elif any(keyword in message for keyword in ["financeiro", "orçamento", "custo"]):
        fallback_content = """**💰 Orientações Financeiras:**
• Mantenha controle rigoroso do fluxo de caixa
• Acompanhe indicadores como ROI e margem de lucro
• Realize análises de viabilidade antes de investir
• Implemente controles internos eficazes
• Gere relatórios regulares para tomada de decisão"""
    
    else:
        fallback_content = f"""Para sua solicitação "{state.current_message}", recomendo configurar agentes especializados:

• **🤖 Agente de Marketing** - Estratégias de comunicação e campanhas
• **💼 Agente de Vendas** - Processos comerciais e gestão de clientes
• **💰 Agente Financeiro** - Análises financeiras e controle de custos

Cada agente pode ser personalizado com conhecimentos específicos da sua empresa."""
    
    fallback_response = AgentResponse(
        agent_id="fallback_system",
        content=fallback_content,
        actions=[],
        confidence=0.6,
        metadata={
            "fallback": True,
            "reason": "no_specialized_agents",
            "suggestion": "configure_agents"
        }
    )
    
    state.add_response(fallback_response)
    state.previous_agent_id = state.current_agent_id
    state.current_agent_id = "fallback_system"
    state.is_complete = True
    
    processing_time = time.time() - start_time
    state.processing_times["fallback_system"] = processing_time
    
    return state