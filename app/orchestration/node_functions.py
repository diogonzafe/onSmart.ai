# app/orchestration/node_functions.py - Versão corrigida

from typing import Dict, List, Any, Optional
import logging
import time
from datetime import datetime

from app.orchestration.state_manager import AgentState, AgentResponse, AgentAction
from app.agents import create_agent
from app.models.agent import AgentType

logger = logging.getLogger(__name__)

# app/orchestration/node_functions.py - Função supervisor_node corrigida

async def supervisor_node(state: AgentState) -> AgentState:
    """
    Nó do supervisor que coordena o fluxo de trabalho.
    CORRIGIDO para funcionar sem agente supervisor, fazendo roteamento inteligente.
    
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
        
        if supervisor_agents:
            # FLUXO COM SUPERVISOR: Usar agente supervisor existente
            logger.info(f"Usando agente supervisor: {supervisor_agents[0].id}")
            
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
        
        else:
            # FLUXO SEM SUPERVISOR: Roteamento inteligente automático
            logger.info("Nenhum agente supervisor encontrado, fazendo roteamento inteligente automático")
            
            # Analisar a mensagem para determinar o departamento mais adequado
            department = _analyze_message_for_department(state.current_message)
            
            # Verificar se existe agente para o departamento identificado
            department_agents = []
            if department == "marketing":
                department_agents = await agent_service.list_agents(
                    user_id=state.user_id,
                    agent_type=AgentType.MARKETING,
                    is_active=True
                )
            elif department == "sales":
                department_agents = await agent_service.list_agents(
                    user_id=state.user_id,
                    agent_type=AgentType.SALES,
                    is_active=True
                )
            elif department == "finance":
                department_agents = await agent_service.list_agents(
                    user_id=state.user_id,
                    agent_type=AgentType.FINANCE,
                    is_active=True
                )
            
            if department_agents:
                # Criar resposta indicando o roteamento automático
                auto_response = AgentResponse(
                    agent_id="auto_supervisor",
                    content=f"Analisando sua solicitação sobre '{state.current_message[:100]}...', identifiquei que se trata de uma questão relacionada a {department}. Vou encaminhar para o agente especializado apropriado.",
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
                
                # Atualizar o estado
                state.add_response(auto_response)
                state.current_agent_id = "auto_supervisor"
                state.next_agent_id = department
                
                logger.info(f"Roteamento automático: {department} (agente disponível)")
            
            else:
                # Tentar encontrar qualquer agente ativo do usuário
                all_user_agents = []
                for agent_type in [AgentType.MARKETING, AgentType.SALES, AgentType.FINANCE]:
                    agents = await agent_service.list_agents(
                        user_id=state.user_id,
                        agent_type=agent_type,
                        is_active=True
                    )
                    all_user_agents.extend(agents)
                
                if all_user_agents:
                    # Há agentes, mas não do tipo identificado - usar o primeiro disponível
                    fallback_agent = all_user_agents[0]
                    fallback_dept = fallback_agent.type.value
                    
                    fallback_response = AgentResponse(
                        agent_id="auto_supervisor_fallback",
                        content=f"Não encontrei um agente especializado em {department}, mas tenho um agente de {fallback_dept} disponível que pode ajudar. Vou encaminhar sua solicitação.",
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
                    
                    logger.info(f"Fallback para agente disponível: {fallback_dept}")
                
                else:
                    # Nenhum agente especializado disponível - resposta educativa
                    no_agents_response = AgentResponse(
                        agent_id="system_guidance",
                        content=f"""Para sua pergunta sobre **{state.current_message[:100]}{'...' if len(state.current_message) > 100 else ''}**, eu posso oferecer algumas orientações gerais:

{_generate_general_response(state.current_message, department)}

**Para obter respostas mais específicas e personalizadas, recomendo criar agentes especializados:**

🤖 **Agente de Marketing** - Para estratégias de comunicação, campanhas e análise de mídia
💼 **Agente de Vendas** - Para processos comerciais, negociação e gestão de clientes  
💰 **Agente Financeiro** - Para análises financeiras, orçamentos e controle de custos
👨‍💼 **Agente Supervisor** - Para coordenar múltiplos departamentos em análises complexas

Cada agente pode ser configurado com conhecimentos específicos da sua empresa e processos.""",
                        actions=[],
                        confidence=0.4,
                        metadata={
                            "reason": "no_agents_configured",
                            "suggested_department": department,
                            "suggestion": "create_specialized_agents",
                            "routing_method": "educational_response"
                        }
                    )
                    
                    state.add_response(no_agents_response)
                    state.current_agent_id = "system_guidance"
                    state.is_complete = True
                    
                    logger.info("Nenhum agente disponível - resposta educativa fornecida")
        
        # Registrar tempo de processamento
        processing_time = time.time() - start_time
        agent_id = state.current_agent_id or "supervisor_unknown"
        state.processing_times[agent_id] = processing_time
        
        return state
        
    except Exception as e:
        logger.error(f"Erro no nó supervisor: {str(e)}")
        
        # Resposta de erro com orientação útil
        error_response = AgentResponse(
            agent_id="system_error",
            content=f"""Ocorreu um erro no processamento: {str(e)}

Como alternativa, posso dar algumas orientações gerais para sua pergunta sobre **{state.current_message[:100]}{'...' if len(state.current_message) > 100 else ''}**:

{_generate_general_response(state.current_message, "geral")}

Para evitar este tipo de erro no futuro, verifique se você tem agentes configurados adequadamente.""",
            actions=[],
            confidence=0.1,
            metadata={
                "error": str(e), 
                "error_type": "supervisor_processing_error",
                "suggestion": "check_agent_configuration"
            }
        )
        
        state.add_response(error_response)
        state.current_agent_id = "system_error"
        state.is_complete = True
        
        # Registrar tempo de processamento
        processing_time = time.time() - start_time
        state.processing_times["system_error"] = processing_time
        
        return state


def _analyze_message_for_department(message: str) -> str:
    """
    Analisa a mensagem para determinar qual departamento é mais adequado.
    MELHORADO com análise mais sofisticada.
    
    Args:
        message: Mensagem do usuário
        
    Returns:
        Departamento mais adequado ('marketing', 'sales', 'finance', ou 'custom')
    """
    import re
    
    # Converter para lowercase para análise
    message_lower = message.lower()
    
    # Padrões mais específicos e contextuais
    marketing_patterns = [
        r'\b(marketing|campanha|publicidade|propaganda|comunicação|mídia|social|redes sociais|conteúdo|branding|marca|engajamento|alcance|seo|adwords|facebook|instagram|linkedin|youtube|tiktok|influencer|viral|hashtag|post|stories|feed|bio|perfil|seguidores|likes|shares|impressões|cliques|ctr|cpm|cpc|roas|brand awareness|share of voice|sentiment|buzz|pr|assessoria|imprensa|release|cobertura|blog|artigo|editorial|newsletter|email marketing|landing page|lead magnet|funil|persona|jornada|customer journey|lifecycle|retention|churn)\b',
        r'\b(estratégia.{0,20}(digital|online|comunicação|marca|conteúdo))\b',
        r'\b(análise.{0,20}(mercado|concorrência|mídia|social|engajamento))\b',
        r'\b(gestão.{0,20}(marca|comunidade|crise|reputação))\b'
    ]
    
    sales_patterns = [
        r'\b(vendas|venda|cliente|lead|prospect|pipeline|funil|conversão|oportunidade|negociação|proposta|orçamento|cotação|desconto|comissão|meta|quota|target|forecast|crm|salesforce|hubspot|follow.?up|cold.?call|warm.?lead|qualified|mql|sql|demo|trial|onboarding|upsell|cross.?sell|churn|lifetime.?value|ltv|cac|customer.?acquisition|retention|satisfaction|nps|survey|feedback|testimonial|referral|partnership|channel|distribuidor|revendedor|franquia|territory|account|key.?account|enterprise|smb|b2b|b2c|inside.?sales|field.?sales|telesales|e.?commerce|marketplace|checkout|cart|payment|subscription|recurring|revenue|arr|mrr)\b',
        r'\b(processo.{0,20}(venda|comercial|negociação|fechamento))\b',
        r'\b(estratégia.{0,20}(vendas|comercial|cliente|account))\b',
        r'\b(gestão.{0,20}(cliente|relacionamento|pipeline|territory))\b'
    ]
    
    finance_patterns = [
        r'\b(financeiro|finanças|contábil|contabilidade|orçamento|budget|custo|despesa|receita|faturamento|cobrança|pagamento|fluxo.?caixa|cash.?flow|dre|demonstrativo|balanço|balancete|lucro|prejuízo|margem|ebitda|ebit|roe|roi|roa|payback|npv|vpl|irr|tir|capex|opex|working.?capital|debt|equity|alavancagem|liquidez|solvência|rentabilidade|lucratividade|break.?even|ponto.?equilibrio|análise.?vertical|análise.?horizontal|kpi|métrica|indicador|performance|budget|forecast|planejamento|controle|auditoria|compliance|fiscal|tributário|imposto|icms|ipi|pis|cofins|ir|csll|simples|lucro.?real|lucro.?presumido|depreciation|amortization|provision|accrual|accounts.?payable|accounts.?receivable|inventory|asset|liability|shareholder|stakeholder|dividend|distribution|valuation|m&a|merger|acquisition|ipo|funding|investment|venture.?capital|private.?equity)\b',
        r'\b(análise.{0,20}(financeira|econômica|custo|benefício|viabilidade|investimento))\b',
        r'\b(controle.{0,20}(interno|gestão|orçamentário|financeiro))\b',
        r'\b(relatório.{0,20}(financeiro|gerencial|contábil))\b'
    ]
    
    # Análise contextual - considerar combinações de termos
    context_scores = {
        "marketing": 0,
        "sales": 0, 
        "finance": 0
    }
    
    # Pontuação por padrões diretos
    for pattern in marketing_patterns:
        matches = len(re.findall(pattern, message_lower))
        context_scores["marketing"] += matches * 2
    
    for pattern in sales_patterns:
        matches = len(re.findall(pattern, message_lower))
        context_scores["sales"] += matches * 2
    
    for pattern in finance_patterns:
        matches = len(re.findall(pattern, message_lower))
        context_scores["finance"] += matches * 2
    
    # Análise de contexto multi-departamental
    multi_dept_indicators = {
        "estratégia integrada": ["marketing", "sales"],
        "impacto nas vendas": ["marketing", "sales"],
        "análise completa": ["marketing", "sales", "finance"],
        "roi": ["marketing", "finance"],
        "custo de aquisição": ["marketing", "sales", "finance"],
        "lifetime value": ["sales", "finance"],
        "budget marketing": ["marketing", "finance"],
        "performance comercial": ["sales", "finance"]
    }
    
    for indicator, depts in multi_dept_indicators.items():
        if indicator in message_lower:
            for dept in depts:
                context_scores[dept] += 1
    
    # Análise de intent - palavras que indicam ação
    action_words = ["preciso", "quero", "análise", "estratégia", "como", "quando", "onde", "qual", "melhor", "otimizar", "melhorar", "aumentar", "reduzir"]
    has_action_intent = any(word in message_lower for word in action_words)
    
    if has_action_intent:
        # Dar peso extra para departamentos identificados quando há intent de ação
        max_score = max(context_scores.values())
        if max_score > 0:
            for dept, score in context_scores.items():
                if score == max_score:
                    context_scores[dept] += 1
    
    # Determinar departamento vencedor
    max_score = max(context_scores.values())
    if max_score > 0:
        # Retornar o departamento com maior score
        for dept, score in context_scores.items():
            if score == max_score:
                return dept
    
    # Fallback: análise de comprimento e complexidade
    if len(message.split()) > 20:
        return "marketing"  # Mensagens longas frequentemente são sobre estratégia/marketing
    elif any(word in message_lower for word in ["vender", "comprar", "cliente", "preço"]):
        return "sales"
    elif any(word in message_lower for word in ["dinheiro", "custo", "valor", "pagar"]):
        return "finance"
    
    # Default
    return "marketing"


def _generate_general_response(message: str, department: str) -> str:
    """
    Gera uma resposta geral útil baseada na mensagem e departamento identificado.
    
    Args:
        message: Mensagem original do usuário
        department: Departamento identificado
        
    Returns:
        Resposta geral contextualizada
    """
    responses = {
        "marketing": """**📱 Marketing Digital - Orientações Gerais:**

• **Análise de Situação**: Mapeie o posicionamento atual da marca, concorrentes e público-alvo
• **Estratégia Multi-Canal**: Integre social media, content marketing, SEO e paid media
• **Métricas de Performance**: Acompanhe reach, engagement, conversions e ROI por canal
• **Otimização Contínua**: Use A/B testing e análise de dados para refinar campanhas

**Impacto em Vendas**: Marketing eficaz pode aumentar leads qualificados em 20-40%
**Impacto Financeiro**: ROI bem executado pode gerar retorno de 3:1 a 6:1 em marketing digital""",

        "sales": """**💼 Estratégia de Vendas - Diretrizes Fundamentais:**

• **Pipeline Management**: Estruture funil com lead scoring e nurturing adequado
• **Processo de Vendas**: Defina etapas claras de qualificação até fechamento
• **CRM e Analytics**: Implemente sistema para tracking de oportunidades e performance
• **Treinamento de Equipe**: Desenvolva técnicas de consultive selling e objection handling

**Métricas Essenciais**: Conversion rate, ciclo de vendas, ticket médio e LTV
**Integração Marketing**: Vendas + marketing alinhados podem aumentar receita em 38%""",

        "finance": """**💰 Análise Financeira - Aspectos Fundamentais:**

• **Controle de Budget**: Monitore ROI por canal e campaign performance
• **Análise de Custos**: CAC (Customer Acquisition Cost) vs LTV (Lifetime Value)
• **Cash Flow Impact**: Considere timing entre investimento em marketing e retorno em vendas
• **KPIs Financeiros**: Margem de contribuição, payback period e ROAS por investimento

**Recomendação**: Mantenha CAC < 30% do LTV e payback period < 12 meses""",

        "geral": """**🎯 Análise Integrada - Visão Holística:**

• **Marketing**: Foque em estratégias data-driven com métricas claras de ROI
• **Vendas**: Desenvolva processo estruturado com CRM e pipeline management
• **Finanças**: Monitore CAC, LTV e margens para sustentabilidade do crescimento

**Integração é Chave**: Alinhamento entre os três departamentos pode aumentar a eficiência geral em até 35%"""
    }
    
    return responses.get(department, responses["geral"])

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