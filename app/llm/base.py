from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, AsyncGenerator  # Adicione AsyncGenerator aqui
import logging

logger = logging.getLogger(__name__)

class LLMBase(ABC):
    """
    Classe base abstrata para implementações de modelos de linguagem.
    Todas as implementações específicas de LLM devem herdar desta classe.
    """
    
    def __init__(self, model_config: Dict[str, Any]):
        """
        Inicializa o modelo com a configuração fornecida.
        
        Args:
            model_config: Dicionário com configurações específicas do modelo
        """
        self.model_config = model_config
        self.model_name = model_config.get('model_name', 'default')
        self.initialize()
        
    @abstractmethod
    def initialize(self) -> None:
        """
        Inicializa o modelo e quaisquer recursos necessários.
        Deve ser implementado por cada classe derivada.
        """
        pass
    
    @abstractmethod
    async def generate(self, 
                  prompt: str, 
                  max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None,
                  stream: bool = False,
                  **kwargs) -> Union[str, AsyncGenerator[str, None]]:
        """
        Gera texto com base no prompt fornecido.
        
        Args:
            prompt: Texto de entrada para o modelo
            max_tokens: Número máximo de tokens a serem gerados
            temperature: Parâmetro de temperatura para controlar aleatoriedade
            stream: Se True, retorna um gerador para streaming de tokens
            **kwargs: Parâmetros adicionais específicos do modelo
            
        Returns:
            Texto gerado ou um gerador assíncrono para streaming
        """
        pass
    
    @abstractmethod
    async def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Cria embeddings vetoriais para o texto fornecido.
        
        Args:
            text: Texto único ou lista de textos para criar embeddings
            
        Returns:
            Vetor único ou lista de vetores de embeddings
        """
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Retorna informações sobre o modelo.
        
        Returns:
            Dicionário com informações do modelo
        """
        return {
            "model_name": self.model_name,
            "model_type": self.__class__.__name__,
            "config": {k: v for k, v in self.model_config.items() if k != "api_key"}
        }
    
    def __repr__(self) -> str:
        """Representação string do modelo."""
        return f"{self.__class__.__name__}(model_name={self.model_name})"