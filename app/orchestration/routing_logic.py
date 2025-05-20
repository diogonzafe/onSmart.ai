from typing import Dict, List, Any, Optional, Literal, Union
from app.orchestration.state_manager import AgentState

def route_to_department(state: AgentState) -> Literal["marketing", "fallback", "complete"]:
    """
    Decide para qual departamento encaminhar com base no estado atual.
    
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
    
    # Verificar metadados da última resposta
    if state.responses:
        last_response = state.responses[-1]
        metadata = last_response.metadata
        
        selected_dept = metadata.get("selected_department")
        
        # Se o departamento selecionado for marketing, rotear para o nó de marketing
        if selected_dept == "marketing":
            return "marketing"
    
    # Fallback como opção padrão
    return "fallback"

def should_end(state: AgentState) -> bool:
    """
    Verifica se o fluxo deve ser encerrado.
    
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
        return True
    
    # Continuar o fluxo
    return False