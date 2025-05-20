from typing import Dict, List, Any, Optional, Callable, TypeVar
from langgraph.graph import StateGraph
import langgraph.graph as lg
from pydantic import BaseModel

from app.orchestration.state_manager import AgentState
from app.orchestration.node_functions import supervisor_node, marketing_node, fallback_node
from app.orchestration.routing_logic import route_to_department, should_end

class GraphBuilder:
    """
    Construtor do grafo de agentes usando LangGraph.
    Define a estrutura e fluxo de trabalho entre os diferentes tipos de agentes.
    """
    
    def __init__(self, db_session):
        """
        Inicializa o construtor de grafo.
        
        Args:
            db_session: Sessão do banco de dados
        """
        self.db_session = db_session
        self.node_functions = {}
    
    def register_node_function(self, name: str, func: Callable) -> None:
        """
        Registra uma função de nó para o grafo.
        
        Args:
            name: Nome do nó
            func: Função a ser executada pelo nó
        """
        self.node_functions[name] = func
    
    def build_agent_graph(self) -> StateGraph:
        """
        Constrói o grafo de agentes para processamento de mensagens.
        
        Returns:
            Grafo compilado pronto para execução
        """
        # Criar grafo com estado tipado
        graph = StateGraph(AgentState)
        
        # Adicionar nós para cada tipo de agente/função
        graph.add_node("supervisor", supervisor_node)
        graph.add_node("marketing", marketing_node)
        graph.add_node("fallback", fallback_node)
        
        # Adicionar arestas condicionais a partir do supervisor
        graph.add_conditional_edges(
            "supervisor",
            route_to_department,
            {
                "marketing": "marketing",
                "fallback": "fallback",
                "complete": None  # Encerrar o fluxo
            }
        )
        
        # Conectar o nó de marketing de volta ao supervisor
        graph.add_edge("marketing", "supervisor")
        
        # Conectar o nó de fallback de volta ao supervisor
        graph.add_edge("fallback", "supervisor")
        
        # Definir o ponto de entrada do grafo
        graph.set_entry_point("supervisor")
        
        # Adicionar condição de término
        graph.add_edge_filter(should_end)
        
        # Compilar o grafo
        return graph.compile()
    
    def create_execution_graph(self):
        """
        Cria e retorna um grafo executável configurado.
        
        Returns:
            Grafo executável
        """
        # Registrar as funções de nó padrão
        if not self.node_functions:
            self.register_node_function("supervisor", supervisor_node)
            self.register_node_function("marketing", marketing_node)
            self.register_node_function("fallback", fallback_node)
        
        # Construir e retornar o grafo
        return self.build_agent_graph()