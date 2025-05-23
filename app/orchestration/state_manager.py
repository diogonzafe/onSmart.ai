from typing import Dict, List, Any, Optional, Union
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
    
    # Sistema de prioridades
    priorities: Dict[str, int] = Field(default_factory=dict)
    
    # Adicionar campo para a sessão do banco de dados
    db_session: Optional[Any] = None
    
    # CORREÇÃO: Adicionar métodos que faltam
    def set_priority(self, key: str, value: int) -> None:
        """Define uma prioridade."""
        self.priorities[key] = value
    
    def get_priority(self, key: str, default: int = 5) -> int:
        """Obtém uma prioridade."""
        return self.priorities.get(key, default)
    
    def add_fact(self, fact: str) -> None:
        """Adiciona um fato à memória."""
        if fact and fact not in self.facts:
            self.facts.append(fact)
    
    def add_action(self, action: Union[Dict[str, Any], AgentAction]) -> None:
        """Adiciona uma ação ao histórico."""
        if isinstance(action, dict):
            action_obj = AgentAction(
                name=action.get("name", "unknown"),
                params=action.get("params", {}),
                agent_id=action.get("agent_id", "unknown")
            )
        else:
            action_obj = action
        
        self.actions_history.append(action_obj)
    
    def get_context(self) -> Dict[str, Any]:
        """Obtém o contexto atual do estado."""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "current_agent_id": self.current_agent_id,
            "attempt_count": self.attempt_count,
            "is_complete": self.is_complete,
            "priorities": self.priorities,
            "facts_count": len(self.facts),
            "actions_count": len(self.actions_history),
            "responses_count": len(self.responses)
        }
    
    def add_response(self, response: Union[Dict[str, Any], "AgentResponse"]) -> None:
        """Adiciona uma resposta ao histórico."""
        if isinstance(response, dict):
            # Converter dicionário para AgentResponse
            action_list = []
            for action_dict in response.get("actions", []):
                action_list.append(AgentAction(
                    name=action_dict.get("name", "unknown"),
                    params=action_dict.get("params", {}),
                    agent_id=response.get("agent_id", "unknown")
                ))
            
            agent_response = AgentResponse(
                agent_id=response.get("agent_id", "unknown"),
                content=response.get("content", ""),
                actions=action_list,
                confidence=response.get("confidence", 1.0),
                metadata=response.get("metadata", {})
            )
            self.responses.append(agent_response)
        else:
            self.responses.append(response)
        
        # Registrar todas as ações executadas
        latest_response = self.responses[-1]
        for action in latest_response.actions:
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

    class Config:
        arbitrary_types_allowed = True