# app/llm/mcp_llm_service.py
from typing import Dict, List, Any, Optional, Union
import logging
from sqlalchemy.orm import Session

from app.llm.smart_router import get_smart_router
from app.models.conversation import Conversation
from app.models.agent import Agent
from app.models.message import Message, MessageRole
from app.core.mcp import get_mcp_formatter, get_mcp_processor

logger = logging.getLogger(__name__)

class MCPLLMService:
    """
    Serviço que integra o protocolo MCP com o sistema de LLM.
    Responsável por preparar o contexto, enviar ao LLM e processar respostas.
    """
    
    def __init__(self):
        self.smart_router = get_smart_router()
        self.formatter = get_mcp_formatter()
        self.processor = get_mcp_processor()
    
    async def generate_agent_response(
        self,
        db: Session,
        conversation_id: str,
        agent: Agent,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gera uma resposta do agente para a conversa atual usando o protocolo MCP.
        
        Args:
            db: Sessão do banco de dados
            conversation_id: ID da conversa
            agent: Agente que responderá
            user_id: ID do usuário (opcional, para rate limiting)
            
        Returns:
            Resposta processada com ações e conteúdo
        """
        # Obter a conversa
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversa não encontrada: {conversation_id}")
        
        # Formatar o contexto MCP
        context = self.formatter.format_conversation_context(
            db=db,
            agent=agent,
            conversation=conversation
        )
        
        # Converter para prompt do LLM
        prompt = self._context_to_prompt(context)
        
        # Gerar resposta via LLM
        model_id = agent.template.llm_config.get("model") if agent.template and agent.template.llm_config else None
        max_tokens = agent.template.llm_config.get("max_tokens", 1024) if agent.template and agent.template.llm_config else 1024
        temperature = agent.template.llm_config.get("temperature", 0.7) if agent.template and agent.template.llm_config else 0.7
        
        response_text = await self.smart_router.smart_generate(
            prompt=prompt,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            user_id=user_id
        )
        
        # Processar resposta
        processed = self.processor.process_response(response_text)
        
        # Salvar a resposta na conversa
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole.AGENT,
            content=processed["filtered_content"],
            metadata={
                "actions": processed["actions"],
                "validation": processed["validation"]
            }
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Incluir a mensagem no resultado
        processed["message"] = {
            "id": message.id,
            "content": message.content,
            "role": message.role.value,
            "created_at": message.created_at
        }
        
        return processed
    
    def _context_to_prompt(self, context: Dict[str, Any]) -> str:
        """
        Converte o contexto MCP para um prompt formatado para o LLM.
        
        Args:
            context: Contexto MCP formatado
            
        Returns:
            Prompt formatado para o LLM
        """
        prompt = ""
        
        # Adicionar prompt do sistema
        system_msg = next((m for m in context["messages"] if m["role"] == "system"), None)
        if system_msg:
            prompt += f"<system>\n{system_msg['content']}\n</system>\n\n"
            
        # Adicionar mensagens na ordem correta (excluindo o prompt do sistema)
        user_assistant_messages = [m for m in context["messages"] if m["role"] != "system"]
        
        for msg in user_assistant_messages:
            role = "user" if msg["role"] == "user" else "assistant"
            prompt += f"<{role}>\n{msg['content']}\n</{role}>\n\n"
        
        # Adicionar contexto sobre ferramentas se existirem
        if context["tools"]:
            tools_desc = "<tools>\n"
            for tool in context["tools"]:
                tools_desc += f"- {tool['name']}: {tool['description']}\n"
            tools_desc += "</tools>\n\n"
            prompt += tools_desc
        
        # Adicionar dados de memória se forem relevantes
        if context.get("memory", {}).get("key_points"):
            key_points = context["memory"]["key_points"]
            if key_points:
                memory_text = "<memory>\nPontos importantes a lembrar:\n"
                for point in key_points[:3]:  # Limitar a 3 pontos para não sobrecarregar
                    memory_text += f"- {point}\n"
                memory_text += "</memory>\n\n"
                prompt += memory_text
                
        # Finalizar com uma instrução para o assistente responder
        prompt += "<assistant>\n"
        
        return prompt

# Singleton para acesso global
_mcp_llm_service = None

def get_mcp_llm_service() -> MCPLLMService:
    """Obtém a instância do serviço MCP LLM."""
    global _mcp_llm_service
    if _mcp_llm_service is None:
        _mcp_llm_service = MCPLLMService()
    return _mcp_llm_service