# app/agents/sales.py
from typing import Dict, List, Any, Optional
import logging
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.models.agent import Agent
from app.models.message import Message

logger = logging.getLogger(__name__)

class SalesAgent(BaseAgent):
    """
    Agente especializado em vendas e negociação.
    Responsável por tarefas como prospecção, qualificação de leads, 
    negociação, fechamento de vendas e pós-venda.
    """
    
    def __init__(self, db: Session, agent_record: Agent, **kwargs):
        """
        Inicializa o agente de vendas.
        
        Args:
            db: Sessão do banco de dados
            agent_record: Registro do agente no banco de dados
        """
        super().__init__(db, agent_record, **kwargs)
        
        # Configurações específicas para vendas
        self.sales_type = self.configuration.get("sales_type", "b2b")  # b2b, b2c, etc.
        self.products = self.configuration.get("products", [])
        self.sales_process = self.configuration.get("sales_process", ["prospecting", "qualifying", "presenting", "closing", "following_up"])
        
        # Definir prioridades específicas
        self.state.set_priority("customer_satisfaction", 9)
        self.state.set_priority("closing_ability", 8)
        self.state.set_priority("product_knowledge", 8)
        
        logger.info(f"Agente de vendas inicializado. Tipo: {self.sales_type}, Produtos: {len(self.products)}")
    
    async def process_message(self, 
                        conversation_id: str, 
                        message: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Processa uma mensagem relacionada a vendas.
        
        Args:
            conversation_id: ID da conversa
            message: Conteúdo da mensagem
            metadata: Metadados adicionais (opcional)
            
        Returns:
            Dicionário com a resposta processada
        """
        # Atualizar estado
        self.state.update_status("processing")
        
        # Extrair fatos da mensagem
        facts = self.extract_facts(message)
        for fact in facts:
            self.state.add_fact(fact)
        
        # Preparar contexto para o LLM
        context = await self._prepare_context(conversation_id)
        
        # Adicionar conhecimento específico de vendas
        if "metadata" not in context:
            context["metadata"] = {}
        
        context["metadata"]["sales_type"] = self.sales_type
        context["metadata"]["products"] = self.products
        context["metadata"]["sales_process"] = self.sales_process
        
        # Formatar o prompt
        prompt = await self._format_prompt(context)
        
        # Gerar resposta
        response_text = await self._generate_response(prompt)
        
        # Processar a resposta
        processed_response = self.mcp_processor.process_response(response_text)
        
        # Executar ações de vendas (se houver)
        action_results = await self._execute_sales_actions(processed_response.get("actions", []))
        processed_response["action_results"] = action_results
        
        # Salvar a resposta na conversa
        message = await self._save_response(
            conversation_id=conversation_id,
            response_text=response_text,
            processed_response=processed_response
        )
        
        # Incluir a mensagem no resultado
        processed_response["message"] = {
            "id": message.id,
            "content": message.content,
            "role": message.role.value,
            "created_at": message.created_at.isoformat()
        }
        
        return processed_response
    
    async def _execute_sales_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executa ações específicas de vendas.
        
        Args:
            actions: Lista de ações a serem executadas
            
        Returns:
            Resultados das ações executadas
        """
        results = []
        
        for action in actions:
            action_name = action.get("name", "")
            params = action.get("params", {})
            
            try:
                # Implementar ações específicas de vendas
                if action_name == "qualify_lead":
                    # Simular qualificação de lead
                    result = {
                        "action": action_name,
                        "status": "success",
                        "result": f"Lead {params.get('lead_id', 'desconhecido')} qualificado como {params.get('qualification', 'prospect')}"
                    }
                
                elif action_name == "create_proposal":
                    # Simular criação de proposta
                    result = {
                        "action": action_name,
                        "status": "success",
                        "result": f"Proposta criada para cliente {params.get('client_name', 'cliente')} com valor de {params.get('value', '$0')}"
                    }
                
                elif action_name == "schedule_follow_up":
                    # Simular agendamento de follow-up
                    result = {
                        "action": action_name,
                        "status": "success",
                        "result": f"Follow-up agendado para {params.get('date', 'amanhã')}"
                    }
                
                else:
                    # Ação genérica
                    result = await super()._execute_actions([action])[0]
                
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
                
                logger.error(f"Erro ao executar ação de vendas {action_name}: {str(e)}")
            
            results.append(result)
        
        return results