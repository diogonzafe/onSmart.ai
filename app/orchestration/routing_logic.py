# app/orchestration/routing_logic.py - Versão corrigida

from typing import Dict, List, Any, Optional, Literal, Union
from app.orchestration.state_manager import AgentState

def route_to_department(state: AgentState) -> Literal["marketing", "sales", "finance", "fallback", "complete"]:
    """
    Decide para qual departamento encaminhar com base no estado atual.
    MELHORADO para trabalhar com roteamento automático.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Nome do próximo nó
    """
    # Se o fluxo estiver completo, não rotear para nenhum departamento
    if state.is_complete:
        return "complete"
    
    # Se precisar de fallback, rotear para o nó de fallback
    if state.requires_fallback:
        return "fallback"
    
    # Verificar se há um próximo agente definido (para roteamento automático)
    if state.next_agent_id:
        next_dept = state.next_agent_id
        # Limpar o next_agent_id para evitar loops
        state.next_agent_id = None
        
        # Verificar se é um departamento válido
        valid_departments = ["marketing", "sales", "finance"]
        if next_dept in valid_departments:
            return next_dept
    
    # Verificar metadados da última resposta (lógica original)
    if state.responses:
        last_response = state.responses[-1]
        metadata = last_response.metadata
        
        selected_dept = metadata.get("selected_department")
        
        # Rotear com base no departamento selecionado
        if selected_dept == "marketing":
            return "marketing"
        elif selected_dept == "sales":
            return "sales"
        elif selected_dept == "finance":
            return "finance"
    
    # Fallback como opção padrão
    return "fallback"


def should_end(state: AgentState) -> bool:
    """
    Verifica se o fluxo deve ser encerrado.
    MELHORADO com lógica mais robusta.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        True se o fluxo deve ser encerrado, False caso contrário
    """
    # Encerrar se indicado explicitamente
    if state.is_complete:
        return True
    
    # Encerrar se atingiu o número máximo de tentativas
    if state.attempt_count >= state.max_attempts:
        state.is_complete = True
        return True
    
    # Encerrar se não há agentes especializados e já passou pelo supervisor
    if (state.current_agent_id and 
        state.current_agent_id.startswith(("system_", "auto_supervisor", "fallback_")) and
        state.attempt_count > 0):
        state.is_complete = True
        return True
    
    # Encerrar se houve erro crítico
    if (state.current_agent_id and 
        "error" in state.current_agent_id):
        state.is_complete = True
        return True
    
    # Continuar o fluxo
    return False


def determine_next_action(state: AgentState) -> Dict[str, Any]:
    """
    Determina a próxima ação baseada no estado atual.
    Nova função para suporte ao roteamento inteligente.
    
    Args:
        state: Estado atual do fluxo
        
    Returns:
        Dicionário com informações sobre a próxima ação
    """
    # Se não há respostas ainda, precisa passar pelo supervisor
    if not state.responses:
        return {
            "action": "route_to_supervisor",
            "reason": "no_responses_yet"
        }
    
    last_response = state.responses[-1]
    
    # Se a última resposta foi do supervisor ou roteamento automático
    if last_response.agent_id in ["auto_supervisor", "auto_supervisor_fallback"]:
        selected_dept = last_response.metadata.get("selected_department")
        
        if selected_dept in ["marketing", "sales", "finance"]:
            return {
                "action": "route_to_department",
                "department": selected_dept,
                "reason": "supervisor_routing"
            }
    
    # Se já processou com um agente especializado
    if last_response.agent_id not in ["auto_supervisor", "auto_supervisor_fallback", "system_guidance", "system_error"]:
        return {
            "action": "complete_flow",
            "reason": "specialist_processed"
        }
    
    # Se chegou até aqui, provavelmente deve completar
    return {
        "action": "complete_flow",
        "reason": "default_completion"
    }


def analyze_multi_department_request(message: str) -> List[str]:
    """
    Analisa se uma mensagem requer múltiplos departamentos.
    
    Args:
        message: Mensagem do usuário
        
    Returns:
        Lista de departamentos necessários
    """
    message_lower = message.lower()
    departments = []
    
    # Indicadores para cada departamento
    marketing_indicators = ["marketing", "campanha", "mídia", "comunicação", "marca", "conteúdo"]
    sales_indicators = ["vendas", "cliente", "comercial", "negociação", "proposta"]
    finance_indicators = ["financeiro", "orçamento", "custo", "receita", "roi", "lucro"]
    
    # Verificar presença de cada departamento
    if any(indicator in message_lower for indicator in marketing_indicators):
        departments.append("marketing")
    
    if any(indicator in message_lower for indicator in sales_indicators):
        departments.append("sales")
    
    if any(indicator in message_lower for indicator in finance_indicators):
        departments.append("finance")
    
    # Palavras que indicam análise integrada
    integration_words = ["completa", "integrada", "holística", "geral", "impacto", "estratégia"]
    
    if any(word in message_lower for word in integration_words) and len(departments) == 0:
        # Se não identificou departamentos específicos mas pede análise integrada
        departments = ["marketing", "sales", "finance"]
    
    return departments


def get_routing_priority(departments: List[str], message: str) -> str:
    """
    Determina qual departamento deve ser o primário em casos multi-departamentais.
    
    Args:
        departments: Lista de departamentos identificados
        message: Mensagem original
        
    Returns:
        Departamento prioritário
    """
    if len(departments) == 1:
        return departments[0]
    
    if len(departments) == 0:
        return "marketing"  # Default
    
    message_lower = message.lower()
    
    # Palavras que indicam prioridade
    priority_indicators = {
        "marketing": ["estratégia", "campanha", "comunicação", "marca", "digital"],
        "sales": ["vendas", "cliente", "comercial", "negociação", "pipeline"],
        "finance": ["financeiro", "orçamento", "custo", "roi", "análise financeira"]
    }
    
    scores = {}
    for dept in departments:
        score = 0
        for indicator in priority_indicators.get(dept, []):
            score += message_lower.count(indicator)
        scores[dept] = score
    
    # Retornar departamento com maior score
    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    
    # Se houver empate ou nenhum score, usar ordem de prioridade padrão
    priority_order = ["marketing", "sales", "finance"]
    for dept in priority_order:
        if dept in departments:
            return dept
    
    return departments[0]