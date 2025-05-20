from typing import Dict, List, Any, Optional, Union, TypedDict
from pydantic import BaseModel, Field
import json
from datetime import datetime
import uuid

class AgentAction(BaseModel):
    """Ação executada por um agente durante o processamento."""
    name: str
    params: Dict[str, Any] = {}
    agent_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AgentResponse(BaseModel):
    """Resposta de um agente no fluxo de processamento."""
    agent_id: str
    content: str
    actions: List[AgentAction] = []
    confidence: float = 1.0
    metadata: Dict[str, Any] = {}

class AgentState(BaseModel):
    """
    Estado compartilhado entre agentes no grafo de execução.
    Mantém o contexto, histórico e resultados intermediários.
    """
    # Informações da conversa
    conversation_id: str
    user_id: str
    messages: List[Dict[str, Any]] = []
    current_message: str = ""
    
    # Controle de fluxo
    current_agent_id: Optional[str] = None
    previous_agent_id: Optional[str] = None
    next_agent_id: Optional[str] = None
    
    # Resultados e memória compartilhada
    responses: List[AgentResponse] = []
    actions_history: List[AgentAction] = []
    facts: List[str] = []
    
    # Métricas e controle
    start_time: datetime = Field(default_factory=datetime.utcnow)
    processing_times: Dict[str, float] = {}
    attempt_count: int = 0
    max_attempts: int = 3
    
    # Flags de controle
    is_complete: bool = False
    requires_fallback: bool = False
    
    def add_response(self, response: AgentResponse) -> None:
        """Adiciona uma resposta ao histórico."""
        self.responses.append(response)
        
        # Registrar todas as ações executadas
        for action in response.actions:
            self.actions_history.append(action)
    
    def get_final_response(self) -> Optional[str]:
        """Obtém a resposta final para enviar ao usuário."""
        if not self.responses:
            return None
        
        # Por padrão, usar a resposta mais recente
        return self.responses[-1].content
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte o estado para dicionário."""
        return json.loads(self.model_dump_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """Cria uma instância a partir de um dicionário."""
        return cls(**data)