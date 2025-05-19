# app/core/mcp.py
from typing import Dict, List, Any, Optional, Union
import json
import logging
import re
from datetime import datetime

from app.models.message import Message, MessageRole
from app.models.conversation import Conversation
from app.models.agent import Agent
from app.models.tool import Tool
from app.models.agent_tool_mapping import AgentToolMapping
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class MCPFormatter:
    """
    Componente responsável pela formatação de contexto no padrão MCP (Model Context Protocol).
    Implementa as especificações da Anthropic para interação com LLMs.
    """
    
    def __init__(self):
        self.default_system_prompt = "Você é um assistente útil e prestativo."
    
    def format_conversation_context(
        self, 
        db: Session,
        agent: Agent, 
        conversation: Conversation, 
        max_messages: int = 50,
        include_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Formata todo o contexto da conversa no padrão MCP.
        
        Args:
            db: Sessão do banco de dados
            agent: Agente responsável pela conversa
            conversation: Conversa atual
            max_messages: Número máximo de mensagens a incluir
            include_tools: Se deve incluir ferramentas disponíveis
            
        Returns:
            Contexto formatado no padrão MCP
        """
        # Obter histórico de mensagens
        messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).limit(max_messages).all()
        
        # Formatar o contexto MCP
        context = {
            "messages": [],
            "tools": []
        }
        
        # Adicionar o prompt do sistema
        system_prompt = self._get_system_prompt(agent)
        context["messages"].append({
            "role": "system",
            "content": system_prompt
        })
        
        # Adicionar histórico de conversa
        for message in messages:
            formatted_message = self._format_message(message)
            if formatted_message:
                context["messages"].append(formatted_message)
        
        # Adicionar ferramentas disponíveis
        if include_tools:
            context["tools"] = self._get_available_tools(db, agent)
        
        # Adicionar metadados e memória
        context["metadata"] = self._format_metadata(agent, conversation)
        context["memory"] = self._format_memory(agent, conversation, messages)
        
        return context
    
    def _get_system_prompt(self, agent: Agent) -> str:
        """Obtém o prompt do sistema para um agente, baseado no seu template."""
        if not agent.template:
            return self.default_system_prompt
            
        template_text = agent.template.prompt_template
        
        # Substituir variáveis no template com a configuração do agente
        if agent.configuration:
            for key, value in agent.configuration.items():
                placeholder = f"{{{{{key}}}}}"
                template_text = template_text.replace(placeholder, str(value))
        
        return template_text
    
    def _format_message(self, message: Message) -> Optional[Dict[str, Any]]:
        """Formata uma mensagem para o formato MCP."""
        role_mapping = {
            MessageRole.HUMAN: "user",
            MessageRole.AGENT: "assistant",
            MessageRole.SYSTEM: "system"
        }
        
        role = role_mapping.get(message.role)
        if not role:
            logger.warning(f"Tipo de mensagem não suportado: {message.role}")
            return None
        
        formatted = {
            "role": role,
            "content": message.content
        }
        
        # Adicionar metadados se existirem
        if hasattr(message, 'metadata') and message.metadata:
            formatted["metadata"] = message.metadata
        
        return formatted
    
    def _get_available_tools(self, db: Session, agent: Agent) -> List[Dict[str, Any]]:
        """Obtém e formata as ferramentas disponíveis para o agente."""
        tools = []
        
        # Buscar mapeamentos de ferramentas
        tool_mappings = db.query(AgentToolMapping).filter(
            AgentToolMapping.agent_id == agent.id
        ).all()
        
        # Formatar cada ferramenta
        for mapping in tool_mappings:
            tool = db.query(Tool).filter(Tool.id == mapping.tool_id).first()
            if tool and tool.is_active:
                tool_spec = {
                    "type": tool.type.value,
                    "name": tool.name,
                    "description": tool.description or "",
                    "config": self._safe_config(tool.configuration),
                    "permissions": mapping.permissions or {}
                }
                
                tools.append(tool_spec)
        
        return tools
    
    def _safe_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove informações sensíveis da configuração."""
        if not config:
            return {}
            
        safe_config = {}
        sensitive_keys = ['key', 'secret', 'password', 'token', 'credential']
        
        for key, value in config.items():
            # Verificar se é uma chave sensível
            is_sensitive = any(s in key.lower() for s in sensitive_keys)
            
            if is_sensitive:
                safe_config[key] = "******"  # Mascarar valor sensível
            else:
                safe_config[key] = value
                
        return safe_config
    
    def _format_metadata(self, agent: Agent, conversation: Conversation) -> Dict[str, Any]:
        """Formata metadados sobre a conversa e agente."""
        metadata = {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_type": agent.type.value,
            "conversation_id": conversation.id,
            "conversation_title": conversation.title,
            "department": agent.template.department.value if agent.template else "unknown"
        }
        
        # Adicionar metadados da conversa se existirem
        if hasattr(conversation, 'metadata') and conversation.metadata:
            metadata["conversation_metadata"] = conversation.metadata
            
        return metadata
    
    def _format_memory(
        self, 
        agent: Agent, 
        conversation: Conversation, 
        messages: List[Message]
    ) -> Dict[str, Any]:
        """
        Implementa um sistema simples de memória para o agente.
        
        Isso inclui:
        - Informações sobre o contexto da conversa
        - Dados extraídos de mensagens anteriores
        - Memória personalizada do agente
        """
        memory = {
            "entities": self._extract_entities(messages),
            "key_points": self._extract_key_points(messages),
            "user_preferences": self._extract_user_preferences(messages),
            "conversation_summary": self._summarize_conversation(conversation, messages)
        }
        
        # Adicionar memória personalizada do agente se existir
        if agent.configuration and "memory" in agent.configuration:
            memory["custom"] = agent.configuration["memory"]
            
        return memory
    
    def _extract_entities(self, messages: List[Message]) -> Dict[str, Any]:
        """
        Extrai entidades mencionadas nas mensagens.
        Implementação básica - em produção, isto poderia usar NER.
        """
        entities = {
            "people": [],
            "organizations": [],
            "dates": [],
            "locations": []
        }
        
        # Implementação simplificada - apenas detecta padrões básicos
        for message in messages:
            if message.role != MessageRole.HUMAN:
                continue
                
            content = message.content.lower()
            
            # Datas - padrão simples DD/MM/YYYY ou YYYY-MM-DD
            date_patterns = [
                r'\d{2}/\d{2}/\d{4}',
                r'\d{4}-\d{2}-\d{2}'
            ]
            
            for pattern in date_patterns:
                dates = re.findall(pattern, content)
                for date in dates:
                    if date not in entities["dates"]:
                        entities["dates"].append(date)
        
        return entities
    
    def _extract_key_points(self, messages: List[Message]) -> List[str]:
        """
        Extrai pontos-chave das mensagens.
        Implementação básica - apenas extrai frases importantes.
        """
        key_points = []
        important_markers = [
            "importante", "essencial", "crucial", "fundamental",
            "lembre-se", "nota", "atenção", "critical", "key", "important"
        ]
        
        for message in messages:
            if message.role != MessageRole.HUMAN:
                continue
                
            sentences = message.content.split(".")
            for sentence in sentences:
                sentence = sentence.strip()
                if any(marker in sentence.lower() for marker in important_markers):
                    if sentence and sentence not in key_points:
                        key_points.append(sentence)
        
        return key_points
    
    def _extract_user_preferences(self, messages: List[Message]) -> Dict[str, Any]:
        """
        Extrai preferências do usuário a partir das mensagens.
        Implementação básica.
        """
        preferences = {
            "communication_style": None,
            "preferred_formats": []
        }
        
        # Detecção de preferências de comunicação
        style_keywords = {
            "formal": ["formal", "profissional", "técnico"],
            "casual": ["casual", "informal", "relaxado", "amigável"],
            "concise": ["conciso", "breve", "direto", "curto"],
            "detailed": ["detalhado", "completo", "aprofundado"]
        }
        
        # Detecção de formatos preferidos
        format_patterns = {
            "bullet_points": ["lista", "bullet points", "tópicos"],
            "paragraphs": ["parágrafo", "texto", "prosa"],
            "code": ["código", "script", "programação"],
            "table": ["tabela", "matriz", "grid"]
        }
        
        for message in messages:
            if message.role != MessageRole.HUMAN:
                continue
                
            content = message.content.lower()
            
            # Detectar estilo de comunicação
            for style, keywords in style_keywords.items():
                if preferences["communication_style"]:
                    break
                    
                for keyword in keywords:
                    if keyword in content:
                        preferences["communication_style"] = style
                        break
            
            # Detectar formatos preferidos
            for format_name, patterns in format_patterns.items():
                for pattern in patterns:
                    if pattern in content and format_name not in preferences["preferred_formats"]:
                        preferences["preferred_formats"].append(format_name)
        
        return preferences
    
    def _summarize_conversation(self, conversation: Conversation, messages: List[Message]) -> str:
        """
        Cria um resumo simples da conversa.
        Implementação básica - em produção, usaria um LLM para resumir.
        """
        if not messages:
            return ""
            
        human_messages = [m for m in messages if m.role == MessageRole.HUMAN]
        
        if not human_messages:
            return ""
            
        # Resumo simples baseado na primeira e última mensagem
        first_message = human_messages[0].content[:100]
        last_message = human_messages[-1].content[:100]
        
        summary = f"Conversa sobre: {conversation.title}. "
        summary += f"Iniciou com: '{first_message}...'. "
        
        if len(human_messages) > 1:
            summary += f"Mensagem mais recente: '{last_message}...'"
        
        return summary


class MCPResponseProcessor:
    """
    Componente para processamento e validação de respostas no protocolo MCP.
    Responsável por extrair ações, validar outputs e aplicar filtros de segurança.
    """
    
    def __init__(self):
        # Definir padrões para detecção de ações
        self.action_patterns = [
            (r'\{\s*"action"\s*:\s*"([^"]+)"\s*,\s*"params"\s*:\s*(\{.*?\})\s*\}', 'json'),
            (r'<action\s+name=[\'"]([^\'"]+)[\'"]>(.*?)</action>', 'xml'),
            (r'\[\[ACTION:([^\]]+)\]\](.*?)\[\[/ACTION\]\]', 'markdown')
        ]
        
        # Definir termos sensíveis para filtragem
        self.sensitive_terms = [
            "senha", "password", "token", "secret", "api_key", "apikey",
            "credit card", "cartão de crédito", "cvv", "cpf", "social security",
            "senha do banco", "banking password", "chave pix", "número do cartão"
        ]
    
    def process_response(self, response: str) -> Dict[str, Any]:
        """
        Processa uma resposta do LLM no formato MCP.
        
        Args:
            response: Texto da resposta do LLM
            
        Returns:
            Resposta processada com ações extraídas e conteúdo filtrado
        """
        # Estrutura para armazenar o resultado
        result = {
            "content": response,
            "actions": [],
            "detected_entities": [],
            "validation": {
                "is_valid": True,
                "warnings": [],
                "filtered_content": response
            }
        }
        
        # Extrair ações
        actions, cleaned_content = self._extract_actions(response)
        result["actions"] = actions
        result["content"] = cleaned_content
        
        # Validar e filtrar conteúdo
        validation = self._validate_content(cleaned_content)
        result["validation"] = validation
        
        # Usar o conteúdo filtrado
        if validation["is_valid"]:
            result["filtered_content"] = validation["filtered_content"]
        
        return result
    
    def _extract_actions(self, text: str) -> tuple:
        """
        Extrai ações do texto da resposta.
        
        Args:
            text: Texto da resposta
            
        Returns:
            Tupla (ações extraídas, texto limpo sem marcações de ação)
        """
        actions = []
        cleaned_text = text
        
        # Procurar por padrões de ação
        for pattern, format_type in self.action_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            
            for match in matches:
                try:
                    if format_type == 'json':
                        action_name = match.group(1)
                        params_json = match.group(2)
                        try:
                            params = json.loads(params_json)
                        except json.JSONDecodeError:
                            params = {"raw": params_json}
                    
                    elif format_type == 'xml':
                        action_name = match.group(1)
                        params_text = match.group(2)
                        params = self._parse_params(params_text)
                    
                    elif format_type == 'markdown':
                        parts = match.group(1).split(':', 1)
                        action_name = parts[0].strip()
                        params_text = match.group(2) if len(match.groups()) > 1 else ""
                        if len(parts) > 1:
                            params_text = parts[1].strip() + " " + params_text
                        params = self._parse_params(params_text)
                    
                    else:
                        continue
                    
                    actions.append({
                        "name": action_name,
                        "params": params,
                        "format": format_type,
                        "raw": match.group(0)
                    })
                    
                    # Remover a ação do texto limpo
                    cleaned_text = cleaned_text.replace(match.group(0), "")
                
                except Exception as e:
                    logger.warning(f"Erro ao extrair ação: {str(e)}")
        
        # Limpar espaços em branco extras
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        return actions, cleaned_text
    
    def _parse_params(self, params_text: str) -> Dict[str, Any]:
        """
        Converte texto de parâmetros em um dicionário.
        
        Args:
            params_text: Texto com parâmetros
            
        Returns:
            Dicionário de parâmetros
        """
        params = {}
        
        # Tentar JSON primeiro
        try:
            return json.loads(params_text)
        except:
            pass
        
        # Tentar formato chave=valor
        pairs = re.findall(r'(\w+)\s*=\s*([^,]+)(?:,|$)', params_text)
        for key, value in pairs:
            # Tentar converter para o tipo apropriado
            value = value.strip()
            if value.lower() == 'true':
                params[key] = True
            elif value.lower() == 'false':
                params[key] = False
            elif value.isdigit():
                params[key] = int(value)
            elif re.match(r'^-?\d+(\.\d+)?$', value):
                params[key] = float(value)
            else:
                # Remover aspas se presentes
                params[key] = re.sub(r'^["\'](.*)["\']$', r'\1', value)
        
        if not params:
            params["text"] = params_text.strip()
            
        return params
    
    def _validate_content(self, content: str) -> Dict[str, Any]:
        """
        Valida o conteúdo para segurança e compliance.
        
        Args:
            content: Conteúdo a ser validado
            
        Returns:
            Resultado da validação
        """
        result = {
            "is_valid": True,
            "warnings": [],
            "filtered_content": content
        }
        
        filtered_content = content
        
        # Verificar termos sensíveis
        for term in self.sensitive_terms:
            if term in content.lower():
                result["warnings"].append(f"Termo sensível detectado: '{term}'")
                # Substituir o termo com asteriscos
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                filtered_content = pattern.sub('*' * len(term), filtered_content)
        
        # Verificar se há muitos problemas
        if len(result["warnings"]) > 3:
            result["is_valid"] = False
        
        result["filtered_content"] = filtered_content
        
        return result


# Singleton para acesso global
_mcp_formatter = None
_mcp_processor = None

def get_mcp_formatter() -> MCPFormatter:
    """Obtém a instância do formatador MCP."""
    global _mcp_formatter
    if _mcp_formatter is None:
        _mcp_formatter = MCPFormatter()
    return _mcp_formatter

def get_mcp_processor() -> MCPResponseProcessor:
    """Obtém a instância do processador de respostas MCP."""
    global _mcp_processor
    if _mcp_processor is None:
        _mcp_processor = MCPResponseProcessor()
    return _mcp_processor