# app/services/agent_service.py
from typing import Dict, List, Any, Optional, Union, Type
import logging
from sqlalchemy.orm import Session
import uuid

from app.models.agent import Agent, AgentType
from app.models.template import Template
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.agents import create_agent
from app.templates.base import get_template_manager

logger = logging.getLogger(__name__)

class AgentService:
    """
    Serviço para gerenciamento de agentes.
    Fornece funcionalidades para criar, atualizar, listar e executar agentes.
    """
    
    def __init__(self, db: Session):
        """
        Inicializa o serviço de agentes.
        
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self.template_manager = get_template_manager()
        self._agent_cache = {}  # Cache de instâncias de agentes
    
    def create_agent(self, 
                   user_id: str, 
                   name: str, 
                   description: str, 
                   agent_type: AgentType, 
                   template_id: str, 
                   configuration: Dict[str, Any] = None) -> Agent:
        """
        Cria um novo agente.
        
        Args:
            user_id: ID do usuário proprietário
            name: Nome do agente
            description: Descrição do agente
            agent_type: Tipo do agente
            template_id: ID do template a ser usado
            configuration: Configurações específicas do agente
            
        Returns:
            Instância do agente criado
        """
        # Verificar se o template existe
        template = self.db.query(Template).filter(Template.id == template_id).first()
        if not template:
            logger.error(f"Template {template_id} não encontrado")
            raise ValueError(f"Template {template_id} não encontrado")
        
        # Carregar o template no gerenciador
        processed_template = self.template_manager.load_template(template)
        
        # Validar configuração contra as variáveis do template
        if configuration:
            try:
                self.template_manager._validate_variables(
                    processed_template["variables"], 
                    configuration
                )
            except ValueError as e:
                logger.error(f"Configuração inválida para o template: {str(e)}")
                raise ValueError(f"Configuração inválida para o template: {str(e)}")
        
        # Criar o agente
        agent = Agent(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            user_id=user_id,
            type=agent_type,
            template_id=template_id,
            configuration=configuration or {},
            is_active=True
        )
        
        # Salvar no banco de dados
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        
        logger.info(f"Agente criado: {name} ({agent.id}) com template {template_id}")
        return agent
    
    def update_agent(self, 
                   agent_id: str, 
                   name: Optional[str] = None, 
                   description: Optional[str] = None, 
                   is_active: Optional[bool] = None,
                   configuration: Optional[Dict[str, Any]] = None) -> Agent:
        """
        Atualiza um agente existente.
        
        Args:
            agent_id: ID do agente a ser atualizado
            name: Novo nome (opcional)
            description: Nova descrição (opcional)
            is_active: Novo status (opcional)
            configuration: Novas configurações (opcional)
            
        Returns:
            Agente atualizado
        """
        # Buscar o agente
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            logger.error(f"Agente {agent_id} não encontrado")
            raise ValueError(f"Agente {agent_id} não encontrado")
        
        # Atualizar campos
        if name is not None:
            agent.name = name
        
        if description is not None:
            agent.description = description
        
        if is_active is not None:
            agent.is_active = is_active
        
        if configuration is not None:
            # Verificar se o template existe
            template = self.db.query(Template).filter(Template.id == agent.template_id).first()
            if not template:
                logger.error(f"Template {agent.template_id} não encontrado")
                raise ValueError(f"Template {agent.template_id} não encontrado")
            
            # Carregar o template no gerenciador
            processed_template = self.template_manager.load_template(template)
            
            # Validar configuração contra as variáveis do template
            try:
                self.template_manager._validate_variables(
                    processed_template["variables"], 
                    configuration
                )
            except ValueError as e:
                logger.error(f"Configuração inválida para o template: {str(e)}")
                raise ValueError(f"Configuração inválida para o template: {str(e)}")
            
            agent.configuration = configuration
        
        # Aplicar as alterações
        self.db.commit()
        self.db.refresh(agent)
        
        # Limpar cache se existir
        if agent_id in self._agent_cache:
            del self._agent_cache[agent_id]
        
        logger.info(f"Agente atualizado: {agent.name} ({agent_id})")
        return agent
    
    def get_agent(self, agent_id: str) -> Agent:
        """
        Obtém um agente pelo ID.
        
        Args:
            agent_id: ID do agente
            
        Returns:
            Instância do agente
        """
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            logger.error(f"Agente {agent_id} não encontrado")
            raise ValueError(f"Agente {agent_id} não encontrado")
        
        return agent
    
    def list_agents(self, 
                  user_id: str, 
                  agent_type: Optional[AgentType] = None, 
                  is_active: bool = True) -> List[Agent]:
        """
        Lista agentes com filtros.
        
        Args:
            user_id: ID do usuário proprietário
            agent_type: Filtro por tipo de agente (opcional)
            is_active: Filtro por status
            
        Returns:
            Lista de agentes
        """
        query = self.db.query(Agent).filter(Agent.user_id == user_id)
        
        if agent_type:
            query = query.filter(Agent.type == agent_type)
        
        query = query.filter(Agent.is_active == is_active)
        
        return query.all()
    
    def delete_agent(self, agent_id: str) -> bool:
        """
        Remove um agente (soft delete).
        
        Args:
            agent_id: ID do agente
            
        Returns:
            True se bem-sucedido, False caso contrário
        """
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            logger.error(f"Agente {agent_id} não encontrado")
            return False
        
        # Marca como inativo
        agent.is_active = False
        self.db.commit()
        
        # Limpar cache se existir
        if agent_id in self._agent_cache:
            del self._agent_cache[agent_id]
        
        logger.info(f"Agente desativado: {agent.name} ({agent_id})")
        return True
    
    async def process_message(self, 
                        agent_id: str, 
                        conversation_id: str, 
                        message: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Processa uma mensagem usando um agente.
        
        Args:
            agent_id: ID do agente
            conversation_id: ID da conversa
            message: Texto da mensagem
            metadata: Metadados adicionais (opcional)
            
        Returns:
            Resposta processada
        """
        # Verificar se a conversa existe
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.status == ConversationStatus.ACTIVE
        ).first()
        
        if not conversation:
            logger.error(f"Conversa {conversation_id} não encontrada ou inativa")
            raise ValueError(f"Conversa não encontrada ou inativa")
        
        # Verificar se o agente existe e está ativo
        agent_record = self.get_agent(agent_id)
        if not agent_record.is_active:
            logger.error(f"Agente {agent_id} está inativo")
            raise ValueError(f"Agente está inativo")
        
        # Registrar a mensagem do usuário
        user_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=MessageRole.HUMAN,
            content=message,
            metadata=metadata
        )
        
        self.db.add(user_message)
        self.db.commit()
        
        # Obter ou criar instância do agente
        agent_instance = self._get_agent_instance(agent_record)
        
        # Processar a mensagem com o agente
        try:
            response = await agent_instance.process_message(
                conversation_id=conversation_id,
                message=message,
                metadata=metadata
            )
            
            return {
                "user_message": {
                    "id": user_message.id,
                    "content": user_message.content
                },
                "agent_response": response
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem com agente {agent_id}: {str(e)}")
            raise
    
    def _get_agent_instance(self, agent_record: Agent):
        """
        Obtém ou cria uma instância do agente.
        
        Args:
            agent_record: Registro do agente
            
        Returns:
            Instância do agente
        """
        agent_id = agent_record.id
        
        # Verificar no cache
        if agent_id in self._agent_cache:
            return self._agent_cache[agent_id]
        
        # Criar nova instância
        agent_instance = create_agent(
            agent_type=agent_record.type,
            db=self.db,
            agent_record=agent_record
        )
        
        # Armazenar no cache
        self._agent_cache[agent_id] = agent_instance
        
        return agent_instance

# Singleton para acesso global
_agent_service_instance = None

def get_agent_service(db: Session) -> AgentService:
    """
    Obtém ou cria a instância do serviço de agentes.
    
    Args:
        db: Sessão do banco de dados
        
    Returns:
        Instância do AgentService
    """
    global _agent_service_instance
    
    if _agent_service_instance is None:
        _agent_service_instance = AgentService(db)
    
    return _agent_service_instance