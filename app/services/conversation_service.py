# app/services/conversation_service.py - Adicionar novo serviço

from typing import Dict, List, Any, Optional
import logging
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timedelta

from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.models.agent import Agent
from app.services.agent_service import get_agent_service

logger = logging.getLogger(__name__)

class ConversationService:
    """
    Serviço para gerenciamento de conversas.
    """
    
    def __init__(self, db: Session):
        """
        Inicializa o serviço de conversas.
        
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self.agent_service = get_agent_service(db)
    
    async def resume_conversation(self, 
                            conversation_id: str, 
                            message: Optional[str] = None) -> Dict[str, Any]:
        """
        Retoma uma conversa interrompida.
        
        Args:
            conversation_id: ID da conversa
            message: Mensagem adicional (opcional)
            
        Returns:
            Status da retomada
        """
        # Verificar se a conversa existe
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversa {conversation_id} não encontrada")
        
        # Verificar se estava ativa
        if conversation.status != ConversationStatus.ACTIVE:
            conversation.status = ConversationStatus.ACTIVE
            conversation.updated_at = datetime.utcnow()
            self.db.commit()
        
        # Obter o agente associado
        agent = self.db.query(Agent).filter(Agent.id == conversation.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {conversation.agent_id} não encontrado")
        
        # Obter últimas mensagens
        last_messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.desc()).limit(5).all()
        
        # Verificar se há mensagens pendentes (último falante foi human)
        has_pending = (last_messages and last_messages[0].role == MessageRole.HUMAN)
        
        # Se houver mensagem adicional ou mensagem pendente, processar
        if message or has_pending:
            # Se houver mensagem adicional, registrá-la
            if message:
                new_message = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role=MessageRole.HUMAN,
                    content=message,
                    meta_data={"resumed": True}
                )
                
                self.db.add(new_message)
                self.db.commit()
                
                # Usar como mensagem a ser processada
                process_message = message
            else:
                # Usar a última mensagem do humano
                process_message = last_messages[0].content
            
            # Processar a mensagem com o agente
            response = await self.agent_service.process_message(
                agent_id=agent.id,
                conversation_id=conversation_id,
                message=process_message,
                metadata={"resumed": True}
            )
            
            return {
                "status": "resumed_with_response",
                "message_processed": True,
                "response": response
            }
        
        # Se não houver mensagem pendente, apenas retomar
        return {
            "status": "resumed",
            "message_processed": False
        }
    
    def detect_stuck_conversations(self, timeout_minutes: int = 30) -> List[str]:
        """
        Detecta conversas ativas que estão paradas (sem resposta) há muito tempo.
        
        Args:
            timeout_minutes: Tempo limite em minutos
            
        Returns:
            Lista de IDs de conversas paradas
        """
        # Calcular timestamp de corte
        cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        # Buscar conversas ativas atualizadas antes do corte
        stuck_conversations = self.db.query(Conversation).filter(
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.updated_at < cutoff_time
        ).all()
        
        result = []
        
        for conv in stuck_conversations:
            # Verificar última mensagem
            last_message = self.db.query(Message).filter(
                Message.conversation_id == conv.id
            ).order_by(Message.created_at.desc()).first()
            
            # Se última mensagem for do usuário, está parada
            if last_message and last_message.role == MessageRole.HUMAN:
                result.append(conv.id)
        
        return result