# app/llm/deepseek.py
import os
import json
import httpx
from typing import Dict, List, Any, Optional, Union, AsyncGenerator
import logging
import asyncio

from app.llm.base import LLMBase
from app.config import settings

logger = logging.getLogger(__name__)

class DeepSeekLLM(LLMBase):
    """
    Implementação de LLM para modelos DeepSeek usando a API.
    """
    
    def initialize(self) -> None:
        """Inicializa o cliente da API DeepSeek."""
        # Obtém a chave da API das configurações
        self.api_key = self.model_config.get("api_key") or settings.DEEPSEEK_API_KEY
        
        if not self.api_key:
            raise ValueError("API key não encontrada para DeepSeek")
        
        # Define o endpoint da API
        self.api_url = self.model_config.get("api_url", "https://api.deepseek.com/v1")
        
        # Define o modelo específico a ser usado
        self.model_name = self.model_config.get("model_name", "deepseek-chat")
        
        logger.info(f"Cliente DeepSeek inicializado para modelo: {self.model_name}")
    
    async def generate(self, 
                  prompt: str, 
                  max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None,
                  stream: bool = False,
                  **kwargs) -> Union[str, AsyncGenerator[str, None]]:
        """
        Gera texto usando a API DeepSeek.
        
        Args:
            prompt: Texto de entrada
            max_tokens: Número máximo de tokens (padrão: 1024)
            temperature: Controle de aleatoriedade (padrão: 0.7)
            stream: Se True, retorna um gerador para streaming
        
        Returns:
            Texto gerado ou gerador de streaming
        """
        max_tokens = max_tokens or self.model_config.get("max_tokens", 1024)
        temperature = temperature or self.model_config.get("temperature", 0.7)
        
        # Prepara a mensagem no formato esperado pela API
        messages = [{"role": "user", "content": prompt}]
        
        # Prepara os parâmetros para a requisição
        request_data = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            **{k: v for k, v in kwargs.items() if k not in ["model", "messages", "max_tokens", "temperature", "stream"]}
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        if stream:
            return self._generate_stream(request_data, headers)
        else:
            # Chamada síncrona
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{self.api_url}/chat/completions",
                        headers=headers,
                        json=request_data,
                        timeout=60.0
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Erro na API DeepSeek: {response.status_code} - {response.text}")
                        raise Exception(f"Erro na API: {response.status_code} - {response.text}")
                    
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                
                except Exception as e:
                    logger.error(f"Erro ao chamar API DeepSeek: {str(e)}")
                    raise
    
    async def _generate_stream(self, 
                          request_data: Dict[str, Any],
                          headers: Dict[str, str]) -> AsyncGenerator[str, None]:
        """
        Gera texto em formato de stream a partir da API DeepSeek.
        
        Args:
            request_data: Dados da requisição
            headers: Cabeçalhos HTTP
        
        Yields:
            Pedaços de texto gerados
        """
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=request_data,
                    timeout=120.0
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.text()
                        logger.error(f"Erro na API DeepSeek: {response.status_code} - {error_text}")
                        raise Exception(f"Erro na API: {response.status_code} - {error_text}")
                    
                    # Processar a resposta de streaming
                    async for chunk in response.aiter_lines():
                        if not chunk.strip():
                            continue
                        
                        if chunk.startswith("data: "):
                            chunk = chunk[6:]  # Remove o prefixo "data: "
                        
                        # Pula a mensagem "[DONE]"
                        if chunk == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(chunk)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            logger.warning(f"Erro ao decodificar chunk JSON: {chunk}")
            
            except Exception as e:
                logger.error(f"Erro durante streaming da API DeepSeek: {str(e)}")
                raise
    
    async def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Cria embeddings para o texto usando a API DeepSeek.
        
        Args:
            text: Texto ou lista de textos
            
        Returns:
            Vetor de embedding ou lista de vetores
        """
        # Prepara os textos em formato de lista
        if isinstance(text, str):
            texts = [text]
        else:
            texts = text
        
        # Prepara a requisição
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        request_data = {
            "model": self.model_config.get("embedding_model", "deepseek-embed"),
            "input": texts
        }
        
        # Faz a chamada para a API
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/embeddings",
                    headers=headers,
                    json=request_data,
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Erro na API DeepSeek: {response.status_code} - {response.text}")
                    raise Exception(f"Erro na API: {response.status_code} - {response.text}")
                
                result = response.json()
                embeddings = [item["embedding"] for item in result["data"]]
                
                # Retorna um único embedding ou uma lista dependendo da entrada
                return embeddings[0] if isinstance(text, str) else embeddings
            
            except Exception as e:
                logger.error(f"Erro ao obter embeddings da API DeepSeek: {str(e)}")
                raise