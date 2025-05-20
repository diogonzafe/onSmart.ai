# app/agents/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
import logging
import uuid
import asyncio
from datetime import datetime

from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.core.mcp import MCPFormatter, MCPResponseProcessor
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class AgentState:
    """
    Classe para gerenciar o estado interno de um agente durante sua execução.
    Mantém informações de contexto, memória de curto prazo e status da execução.
    """
    
    def __init__(self):
        self.context: Dict[str, Any] = {}
        self.memory: Dict[str, Any] = {
            "facts": [],
            "recent_actions": [],
            "priorities": []
        }
        self.status: str = "idle"  # idle, processing, waiting, error
        self.error: Optional[str] = None
        self.last_update: datetime = datetime.utcnow()
        
    def update_status(self, status: str, error: Optional[str] = None) -> None:
        """Atualiza o status do agente e registra erro se houver."""
        self.status = status
        self.error = error
        self.last_update = datetime.utcnow()
        
    def add_fact(self, fact: str) -> None:
        """Adiciona um fato à memória do agente."""
        if fact not in self.memory["facts"]:
            self.memory["facts"].append(fact)
            # Limitar para os 20 fatos mais recentes
            self.memory["facts"] = self.memory["facts"][-20:]
    
    def add_action(self, action: Dict[str, Any]) -> None:
        """Registra uma ação realizada pelo agente."""
        self.memory["recent_actions"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action
        })
        # Manter apenas as 10 ações mais recentes
        self.memory["recent_actions"] = self.memory["recent_actions"][-10:]
    
    def set_priority(self, priority: str, value: int) -> None:
        """Define uma prioridade para o agente."""
        # Encontrar e atualizar se já existir
        for p in self.memory["priorities"]:
            if p["name"] == priority:
                p["value"] = value
                return
        
        # Adicionar se não existir
        self.memory["priorities"].append({
            "name": priority,
            "value": value
        })
    
    def get_context(self) -> Dict[str, Any]:
        """Retorna o contexto completo do agente para uso em prompts."""
        return {
            "context": self.context,
            "memory": self.memory,
            "status": self.status,
            "last_update": self.last_update.isoformat()
        }


class BaseAgent(ABC):
    """
    Classe base abstrata para todos os agentes no sistema.
    Define a interface comum e implementa funcionalidades compartilhadas.
    """
    
    def __init__(self, 
                 db: Session,
                 agent_record: Agent,
                 mcp_formatter: Optional[MCPFormatter] = None,
                 mcp_processor: Optional[MCPResponseProcessor] = None):
        """
        Inicializa um agente com base em seu registro no banco de dados.
        
        Args:
            db: Sessão do banco de dados
            agent_record: Registro do agente no banco de dados
            mcp_formatter: Formatador MCP (opcional)
            mcp_processor: Processador MCP (opcional)
        """
        self.db = db
        self.agent_record = agent_record
        self.agent_id = agent_record.id
        self.agent_type = agent_record.type
        self.name = agent_record.name
        self.configuration = agent_record.configuration or {}
        
        # Componentes MCP
        from app.core.mcp import get_mcp_formatter, get_mcp_processor
        self.mcp_formatter = mcp_formatter or get_mcp_formatter()
        self.mcp_processor = mcp_processor or get_mcp_processor()
        
        # Inicializar estado
        self.state = AgentState()
        
        # Carregar configurações específicas do template
        self.template = agent_record.template
        if self.template:
            self.prompt_template = self.template.prompt_template
            self.tools_config = self.template.tools_config
            self.llm_config = self.template.llm_config
        else:
            self.prompt_template = "Você é um assistente útil."
            self.tools_config = {}
            self.llm_config = {}
        
        logger.info(f"Agente inicializado: {self.name} ({self.agent_type})")
    
    @abstractmethod
    async def process_message(self, 
                        conversation_id: str, 
                        message: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Processa uma mensagem recebida e gera uma resposta.
        Método abstrato que deve ser implementado por cada tipo de agente.
        
        Args:
            conversation_id: ID da conversa
            message: Conteúdo da mensagem
            metadata: Metadados adicionais (opcional)
            
        Returns:
            Dicionário com a resposta processada
        """
        pass
    
    async def _prepare_context(self, conversation_id: str) -> Dict[str, Any]:
        """
        Prepara o contexto MCP para uma conversa.
        
        Args:
            conversation_id: ID da conversa
            
        Returns:
            Contexto formatado no padrão MCP
        """
        # Buscar a conversa
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversa não encontrada: {conversation_id}")
        
        # Formatar o contexto usando o formatador MCP
        context = self.mcp_formatter.format_conversation_context(
            db=self.db,
            agent=self.agent_record,
            conversation=conversation
        )
        
        # Adicionar estado atual do agente
        agent_state = self.state.get_context()
        if "metadata" not in context:
            context["metadata"] = {}
        context["metadata"]["agent_state"] = agent_state
        
        return context
    
    async def _format_prompt(self, context: Dict[str, Any]) -> str:
        """
        Formata o prompt para o LLM com base no contexto MCP.
        
        Args:
            context: Contexto MCP
            
        Returns:
            Prompt formatado
        """
        prompt = ""
        
        # Adicionar prompt do sistema
        system_msg = next((m for m in context["messages"] if m["role"] == "system"), None)
        if system_msg:
            prompt += f"<system>\n{system_msg['content']}\n</system>\n\n"
        
        # Adicionar histórico de mensagens
        user_assistant_messages = [m for m in context["messages"] if m["role"] != "system"]
        for msg in user_assistant_messages:
            role = "user" if msg["role"] == "user" else "assistant"
            prompt += f"<{role}>\n{msg['content']}\n</{role}>\n\n"
        
        # Adicionar informações sobre ferramentas disponíveis
        if context.get("tools"):
            tools_desc = "<tools>\n"
            for tool in context["tools"]:
                tools_desc += f"- {tool['name']}: {tool['description']}\n"
            tools_desc += "</tools>\n\n"
            prompt += tools_desc
        
        # Adicionar estado do agente
        agent_state = context.get("metadata", {}).get("agent_state")
        if agent_state:
            memory = agent_state.get("memory", {})
            if memory.get("facts"):
                facts_text = "<facts>\n"
                for fact in memory["facts"]:
                    facts_text += f"- {fact}\n"
                facts_text += "</facts>\n\n"
                prompt += facts_text
        
        # Finalizar prompt para o assistente responder
        prompt += "<assistant>\n"
        
        return prompt
    
    async def _generate_response(self, prompt: str) -> str:
        """
        Gera uma resposta usando o LLM configurado para o agente.
        
        Args:
            prompt: Prompt formatado
            
        Returns:
            Texto da resposta
        """
        # Lazy import para evitar importação circular
        from app.llm.smart_router import get_smart_router
        
        # Obter o router
        smart_router = get_smart_router()
        
        # Configurações do LLM
        model_id = self.llm_config.get("model")
        max_tokens = self.llm_config.get("max_tokens", 1024)
        temperature = self.llm_config.get("temperature", 0.7)
        
        # Gerar resposta
        response = await smart_router.smart_generate(
            prompt=prompt,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response
    
    async def _save_response(self, 
                       conversation_id: str, 
                       response_text: str,
                       processed_response: Dict[str, Any]) -> Message:
        """
        Salva a resposta na conversa.
        
        Args:
            conversation_id: ID da conversa
            response_text: Texto da resposta
            processed_response: Resposta processada com ações extraídas
            
        Returns:
            Mensagem salva
        """
        # Criar a mensagem
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole.AGENT,
            content=processed_response["filtered_content"],
            metadata={
                "actions": processed_response["actions"],
                "validation": processed_response["validation"]
            }
        )
        
        # Registrar no banco de dados
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        # Atualizar estado do agente
        self.state.update_status("idle")
        
        # Registrar ações executadas
        for action in processed_response["actions"]:
            self.state.add_action(action)
        
        return message
    
    async def _execute_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executa ações especificadas pelo agente.
        
        Args:
            actions: Lista de ações a serem executadas
            
        Returns:
            Resultados das ações executadas
        """
        results = []
        
        for action in actions:
            action_name = action.get("name")
            params = action.get("params", {})
            
            try:
                # Implementar a lógica de execução de ações específicas
                # Este é um placeholder que pode ser sobrescrito por agentes específicos
                result = {
                    "action": action_name,
                    "status": "success",
                    "result": f"Ação {action_name} simulada com parâmetros {params}"
                }
                
                # Registrar no estado
                self.state.add_action({
                    "name": action_name,
                    "params": params,
                    "status": "success"
                })
                
            except Exception as e:
                result = {
                    "action": action_name,
                    "status": "error",
                    "error": str(e)
                }
                
                # Registrar erro no estado
                self.state.add_action({
                    "name": action_name,
                    "params": params,
                    "status": "error",
                    "error": str(e)
                })
                
                logger.error(f"Erro ao executar ação {action_name}: {str(e)}")
            
            results.append(result)
        
        return results
    
    def extract_facts(self, text: str) -> List[str]:
        """
        Extrai fatos relevantes de um texto para memória do agente.
        
        Args:
            text: Texto para extrair fatos
            
        Returns:
            Lista de fatos extraídos
        """
        # Implementação básica - pode ser melhorada com NLP
        facts = []
        
        # Dividir por frases e filtrar
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
        
        # Procurar por indicadores de fatos
        indicators = [
            "é", "são", "foi", "foram", "consiste", "significa",
            "define", "representa", "contém", "inclui", "exclui",
            "maior", "menor", "importante", "essencial", "crítico"
        ]
        
        for sentence in sentences:
            if any(ind in sentence.lower() for ind in indicators):
                facts.append(sentence)
        
        return facts[:5]  # Limitar a 5 fatos por processamento