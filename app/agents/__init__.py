# app/agents/__init__.py
from app.agents.base import BaseAgent, AgentState
from app.agents.supervisor import SupervisorAgent
from app.agents.marketing import MarketingAgent
from app.agents.sales import SalesAgent
from app.agents.finance import FinanceAgent

# Factory function para criar o tipo apropriado de agente
def create_agent(agent_type, db, agent_record, **kwargs):
    """
    Cria uma instância do tipo apropriado de agente com base no tipo do registro.
    
    Args:
        agent_type: Tipo do agente a ser criado
        db: Sessão do banco de dados
        agent_record: Registro do agente no banco de dados
        **kwargs: Argumentos adicionais para o construtor do agente
        
    Returns:
        Instância do agente criado
    """
    from app.models.agent import AgentType
    
    agent_map = {
        AgentType.SUPERVISOR: SupervisorAgent,
        AgentType.MARKETING: MarketingAgent,
        AgentType.SALES: SalesAgent,
        AgentType.FINANCE: FinanceAgent,
        AgentType.CUSTOM: BaseAgent
    }
    
    agent_class = agent_map.get(agent_type, BaseAgent)
    return agent_class(db, agent_record, **kwargs)