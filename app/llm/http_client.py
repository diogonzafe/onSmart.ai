# app/llm/http_client.py
import httpx
from typing import Dict, List, Any, Optional, Union, AsyncGenerator
import logging
import json
import asyncio

from app.llm.base import LLMBase
from app.config import settings

logger = logging.getLogger(__name__)

class HttpLLM(LLMBase):
    """
    Implementação de LLM que se conecta ao servidor LLM interno.
    """
    
    def initialize(self) -> None:
        """Inicializa a conexão com o servidor LLM."""
        self.server_url = self.model_config.get("server_url") or settings.LLM_SERVER_URL
        self.timeout = self.model_config.get("timeout") or settings.LLM_SERVER_TIMEOUT
        
        if not self.server_url:
            raise ValueError("server_url não encontrado para HttpLLM")
        
        logger.info(f"Cliente HTTP LLM inicializado para servidor: {self.server_url}")
    
    async def generate(self, 
                  prompt: str, 
                  max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None,
                  stream: bool = False,
                  **kwargs) -> Union[str, AsyncGenerator[str, None]]:
        """
        Gera texto usando o servidor LLM interno.
        """
        max_tokens = max_tokens or self.model_config.get("max_tokens", 256)
        temperature = temperature or self.model_config.get("temperature", 0.7)
        
        # Prepara a requisição
        request_data = {
            "prompt": prompt,
            "model_id": self.model_config.get("target_model", "llama"),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            **{k: v for k, v in kwargs.items() if k not in ["prompt", "model_id", "max_tokens", "temperature", "stream"]}
        }
        
        if stream:
            return self._generate_stream(request_data)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(
                        f"{self.server_url}/generate",
                        json=request_data
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Erro no servidor LLM: {response.status_code} - {response.text}")
                        raise Exception(f"Erro no servidor: {response.status_code} - {response.text}")
                    
                    result = response.json()
                    return result["text"]
                
                except Exception as e:
                    logger.error(f"Erro ao chamar servidor LLM: {str(e)}")
                    raise
    
    async def _generate_stream(self, request_data: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Gera texto em formato de stream a partir do servidor LLM.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.server_url}/generate",
                    json=request_data
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.text()
                        logger.error(f"Erro no servidor LLM: {response.status_code} - {error_text}")
                        raise Exception(f"Erro no servidor: {response.status_code} - {error_text}")
                    
                    async for chunk in response.aiter_lines():
                        if chunk:
                            try:
                                data = json.loads(chunk)
                                if "text" in data:
                                    yield data["text"]
                            except json.JSONDecodeError:
                                logger.warning(f"Erro ao decodificar chunk JSON: {chunk}")
            
            except Exception as e:
                logger.error(f"Erro durante streaming do servidor LLM: {str(e)}")
                raise
    
    async def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Cria embeddings usando o servidor LLM interno.
        """
        # Prepara a requisição
        request_data = {
            "text": text,
            "model_id": self.model_config.get("target_model", "llama")
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.server_url}/embed",
                    json=request_data
                )
                
                if response.status_code != 200:
                    logger.error(f"Erro no servidor LLM: {response.status_code} - {response.text}")
                    raise Exception(f"Erro no servidor: {response.status_code} - {response.text}")
                
                result = response.json()
                return result["embedding"]
            
            except Exception as e:
                logger.error(f"Erro ao obter embeddings do servidor LLM: {str(e)}")
                raise