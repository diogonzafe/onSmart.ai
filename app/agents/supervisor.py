# app/agents/supervisor.py
from typing import Dict, List, Any, Optional, Union, Type
import logging
import json
import re
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.models.agent import Agent, AgentType
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole

logger = logging.getLogger(__name__)

class SupervisorAgent(BaseAgent):
    """
    Agente supervisor responsável por coordenar outros agentes,
    distribuir tarefas e gerenciar o fluxo de trabalho.
    """
    
    def __init__(self, db: Session, agent_record: Agent, **kwargs):
        """
        Inicializa o agente supervisor.
        
        Args:
            db: Sessão do banco de dados
            agent_record: Registro do agente no banco de dados
        """
        super().__init__(db, agent_record, **kwargs)
        
        # Inicializar dicionário de agentes subordinados
        self.department_agents: Dict[str, List[str]] = {}
        
        # Carregar agentes subordinados do mesmo usuário
        self._load_department_agents()
        
        # Definir prioridades padrão
        self.state.set_priority("accuracy", 8)
        self.state.set_priority("efficiency", 7)
        self.state.set_priority("empathy", 6)
        
        logger.info(f"Agente supervisor inicializado com {sum(len(agents) for agents in self.department_agents.values())} agentes subordinados")
    
    def _load_department_agents(self) -> None:
        """Carrega os agentes subordinados do mesmo usuário."""
        user_id = self.agent_record.user_id
        
        # Consultar agentes que não são supervisores
        agents = self.db.query(Agent).filter(
            Agent.user_id == user_id,
            Agent.type != AgentType.SUPERVISOR,
            Agent.is_active == True
        ).all()
        
        # Organizar por departamento
        for agent in agents:
            dept = agent.type.value
            if dept not in self.department_agents:
                self.department_agents[dept] = []
            
            self.department_agents[dept].append(agent.id)
    
    async def process_message(self, 
                        conversation_id: str, 
                        message: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Processa uma mensagem e determina qual agente especializado deve atendê-la.
        
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
        
        # Adicionar informação sobre agentes disponíveis
        if "metadata" not in context:
            context["metadata"] = {}
        context["metadata"]["available_departments"] = list(self.department_agents.keys())
        
        # Formatar o prompt
        prompt = await self._format_prompt(context)
        
        # Gerar resposta
        response_text = await self._generate_response(prompt)
        
        # Processar a resposta
        processed_response = self.mcp_processor.process_response(response_text)
        
        # Determinar o departamento mais apropriado
        department = self._determine_department(message, processed_response)
        
        # Se houver agentes disponíveis para o departamento, atribuir a tarefa
        if department in self.department_agents and self.department_agents[department]:
            # Por enquanto, apenas registramos qual seria o agente apropriado
            # Em uma implementação completa, delegaríamos a tarefa
            agent_id = self.department_agents[department][0]
            processed_response["metadata"] = processed_response.get("metadata", {})
            processed_response["metadata"]["selected_department"] = department
            processed_response["metadata"]["selected_agent"] = agent_id
            
            self.state.add_action({
                "name": "route_to_department",
                "department": department,
                "agent_id": agent_id
            })
        
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
    
    # Atualizar o método _determine_department em app/agents/supervisor.py

    def _determine_department(self, 
                            message: str, 
                            processed_response: Dict[str, Any]) -> str:
        """
        Determina qual departamento é mais adequado para responder à mensagem.
        
        Args:
            message: Mensagem do usuário
            processed_response: Resposta processada do LLM
            
        Returns:
            Nome do departamento mais adequado
        """
        # Verificar se o LLM especificou um departamento em uma ação
        for action in processed_response.get("actions", []):
            if action.get("name") == "route_to_department":
                department = action.get("params", {}).get("department")
                if department and department in self.department_agents:
                    return department
        
        # Análise de palavras-chave se o LLM não especificou
        keywords = {
            "marketing": ["marketing", "publicidade", "campanha", "redes sociais", "marca", "branding", 
                        "público-alvo", "divulgação", "comunicação", "mídia", "propaganda", "anúncio", 
                        "conteúdo", "site", "blog", "engajamento", "alcance"],
            
            "sales": ["vendas", "cliente", "proposta", "negociação", "desconto", "preço", "cotação", 
                    "compra", "vender", "oportunidade", "lead", "pipeline", "funil", "conversão", 
                    "prospectar", "contrato", "fechar"],
            
            "finance": ["financeiro", "orçamento", "custo", "pagamento", "fatura", "receita", "despesa", 
                    "contabilidade", "investimento", "ROI", "lucro", "prejuízo", "balanço", "fiscal", 
                    "imposto", "tributo", "demonstrativo", "fluxo de caixa"]
        }
        
        # Contar ocorrências de palavras-chave
        scores = {dept: 0 for dept in keywords}
        
        for dept, words in keywords.items():
            for word in words:
                scores[dept] += len(re.findall(rf'\b{word}\b', message.lower()))
        
        # Aplicar pesos contextuais baseados na frequência de termos relacionados
        message_tokens = message.lower().split()
        token_count = len(message_tokens)
        
        # Verificar contexto de ações
        action_words = ["fazer", "criar", "preparar", "elaborar", "desenvolver", "implementar"]
        has_action_context = any(word in message_tokens for word in action_words)
        
        # Verificar contexto de análise
        analysis_words = ["analisar", "verificar", "avaliar", "estudar", "comparar", "medir"]
        has_analysis_context = any(word in message_tokens for word in analysis_words)
        
        # Aplicar ajustes de contexto
        if has_action_context:
            # Ações tendem a favorecer marketing e vendas
            scores["marketing"] *= 1.2
            scores["sales"] *= 1.2
        
        if has_analysis_context:
            # Análises tendem a favorecer finanças
            scores["finance"] *= 1.5
        
        # Retornar o departamento com maior pontuação ou "custom" se empate/nenhum
        max_score = max(scores.values())
        if max_score > 0:
            max_departments = [dept for dept, score in scores.items() if score == max_score]
            return max_departments[0]
        
        # Fallback para tipo personalizado
        return "custom"