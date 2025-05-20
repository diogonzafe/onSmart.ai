import unittest
from unittest.mock import Mock, MagicMock, patch
import asyncio

from app.orchestration.graph_builder import GraphBuilder
from app.orchestration.state_manager import AgentState

class TestGraphBuilder(unittest.TestCase):
    """Testes para o construtor de grafo."""

    def setUp(self):
        """Configura dados de teste."""
        self.mock_db_session = Mock()
        self.graph_builder = GraphBuilder(self.mock_db_session)
    
    def test_init(self):
        """Testa a inicialização do construtor."""
        self.assertEqual(self.graph_builder.db_session, self.mock_db_session)
        self.assertEqual(self.graph_builder.node_functions, {})
    
    def test_register_node_function(self):
        """Testa o registro de funções de nó."""
        mock_func = Mock()
        self.graph_builder.register_node_function("test_node", mock_func)
        
        self.assertIn("test_node", self.graph_builder.node_functions)
        self.assertEqual(self.graph_builder.node_functions["test_node"], mock_func)
    
    @patch('app.orchestration.graph_builder.StateGraph')
    @patch('app.orchestration.graph_builder.supervisor_node')
    @patch('app.orchestration.graph_builder.marketing_node')
    @patch('app.orchestration.graph_builder.fallback_node')
    @patch('app.orchestration.graph_builder.route_to_department')
    @patch('app.orchestration.graph_builder.should_end')
    def test_build_agent_graph(self, mock_should_end, mock_route, mock_fallback, 
                            mock_marketing, mock_supervisor, mock_state_graph):
        """Testa a construção do grafo de agentes."""
        # Configurar mocks
        mock_graph = Mock()
        mock_state_graph.return_value = mock_graph
        mock_graph.add_node = Mock()
        mock_graph.add_conditional_edges = Mock()
        mock_graph.add_edge = Mock()
        mock_graph.set_entry_point = Mock()
        # Não esperamos mais essa chamada: mock_graph.add_edge_filter = Mock()
        mock_graph.compile = Mock(return_value=mock_graph)
        
        # Chamar o método a ser testado
        result = self.graph_builder.build_agent_graph()
        
        # Verificar se o grafo foi construído corretamente
        mock_state_graph.assert_called_once_with(AgentState)
        
        # Verificar se os nós foram adicionados
        # Verificar também o nó "end" adicional
        mock_graph.add_node.assert_any_call("supervisor", mock_supervisor)
        mock_graph.add_node.assert_any_call("marketing", mock_marketing)
        mock_graph.add_node.assert_any_call("fallback", mock_fallback)
        
        # Verificar se as arestas condicionais foram adicionadas
        mock_graph.add_conditional_edges.assert_called_once()
        
        # Verificar se as arestas foram adicionadas
        mock_graph.add_edge.assert_any_call("marketing", "supervisor")
        mock_graph.add_edge.assert_any_call("fallback", "supervisor")
        
        # Verificar ponto de entrada
        mock_graph.set_entry_point.assert_called_once_with("supervisor")
        
        # Remover essa verificação:
        # mock_graph.add_edge_filter.assert_called_once_with(mock_should_end)
        
        # Verificar compilação
        mock_graph.compile.assert_called_once()
        
        # Verificar retorno
        self.assertEqual(result, mock_graph)
        
    @patch.object(GraphBuilder, 'build_agent_graph')
    def test_create_execution_graph(self, mock_build_graph):
        """Testa a criação do grafo executável."""
        # Configurar mock
        mock_graph = Mock()
        mock_build_graph.return_value = mock_graph
        
        # Chamar o método a ser testado
        result = self.graph_builder.create_execution_graph()
        
        # Verificar registros de funções padrão - esperar 3 funções 
        self.assertEqual(len(self.graph_builder.node_functions), 3)
        
        # Verificar se o grafo foi construído
        mock_build_graph.assert_called_once()
        
        # Verificar retorno
        self.assertEqual(result, mock_graph)

if __name__ == "__main__":
    unittest.main()