# app/agents/finance.py
from typing import Dict, List, Any, Optional
import logging
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.models.agent import Agent
from app.models.message import Message

logger = logging.getLogger(__name__)

class FinanceAgent(BaseAgent):
    """
    Agente especializado em finanças e contabilidade.
    Responsável por tarefas como orçamentos, análise financeira, 
    gestão de custos, faturamento e relatórios financeiros.
    """
    
    def __init__(self, db: Session, agent_record: Agent, **kwargs):
        """
        Inicializa o agente financeiro.
        
        Args:
            db: Sessão do banco de dados
            agent_record: Registro do agente no banco de dados
        """
        super().__init__(db, agent_record, **kwargs)
        
        # Configurações específicas para finanças
        self.finance_areas = self.configuration.get("finance_areas", ["budgeting", "analysis", "reporting"])
        self.accounting_standards = self.configuration.get("accounting_standards", ["GAAP"])
        self.currency = self.configuration.get("currency", "BRL")
        
        # Definir prioridades específicas
        self.state.set_priority("accuracy", 10)
        self.state.set_priority("compliance", 9)
        self.state.set_priority("timeliness", 8)
        
        logger.info(f"Agente financeiro inicializado. Áreas: {self.finance_areas}, Moeda: {self.currency}")
    
    async def process_message(self, 
                        conversation_id: str, 
                        message: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Processa uma mensagem relacionada a finanças.
        
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
        
        # Adicionar conhecimento específico de finanças
        if "metadata" not in context:
            context["metadata"] = {}
        
        context["metadata"]["finance_areas"] = self.finance_areas
        context["metadata"]["accounting_standards"] = self.accounting_standards
        context["metadata"]["currency"] = self.currency
        
        # Formatar o prompt
        prompt = await self._format_prompt(context)
        
        # Gerar resposta
        response_text = await self._generate_response(prompt)
        
        # Processar a resposta
        processed_response = self.mcp_processor.process_response(response_text)
        
        # Executar ações financeiras (se houver)
        action_results = await self._execute_finance_actions(processed_response.get("actions", []))
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
    
    async def _execute_finance_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executa ações específicas de finanças.
        
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
                # Implementar ações específicas de finanças
                if action_name == "calculate_budget":
                    # Simular cálculo de orçamento
                    result = {
                        "action": action_name,
                        "status": "success",
                        "result": f"Orçamento calculado para departamento {params.get('department', 'geral')} no valor de {params.get('amount', 0)} {self.currency}"
                    }
                
                elif action_name == "generate_report":
                    # Simular geração de relatório
                    result = {
                        "action": action_name,
                        "status": "success",
                        "result": f"Relatório financeiro gerado para período {params.get('period', 'mensal')}"
                    }
                
                elif action_name == "analyze_expenses":
                    # Simular análise de despesas
                    result = {
                        "action": action_name,
                        "status": "success",
                        "result": f"Análise de despesas realizada para categoria {params.get('category', 'todas')}"
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
                
                logger.error(f"Erro ao executar ação financeira {action_name}: {str(e)}")
            
            results.append(result)
        
        return results