# app/llm/mistral.py
import os
import json
import httpx
from typing import Dict, List, Any, Optional, Union, AsyncGenerator
import logging
import asyncio

from app.llm.base import LLMBase
from app.config import settings

logger = logging.getLogger(__name__)

class MistralLLM(LLMBase):
    """
    Implementação de LLM para modelos Mistral usando a API Mistral.
    """
    
    def initialize(self) -> None:
        """Inicializa o cliente da API Mistral."""
        # Obtém a chave da API das configurações
        self.api_key = self.model_config.get("api_key") or settings.MISTRAL_API_KEY
        
        if not self.api_key:
            raise ValueError("API key não encontrada para Mistral")
        
        # Define o endpoint da API
        self.api_url = self.model_config.get("api_url", "https://api.mistral.ai/v1")
        
        # Define o modelo específico a ser usado
        self.model_name = self.model_config.get("model_name", "mistral-medium")
        
        logger.info(f"Cliente Mistral inicializado para modelo: {self.model_name}")
    
    async def generate(self, 
                  prompt: str, 
                  max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None,
                  stream: bool = False,
                  **kwargs) -> Union[str, AsyncGenerator[str, None]]:
        """
        Gera texto usando a API Mistral.
        
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
        
        # Prepara os parâmetros para a requisição
        request_data = {
            "model": self.model_name,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            **{k: v for k, v in kwargs.items() if k not in ["model", "prompt", "max_tokens", "temperature", "stream"]}
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
                        f"{self.api_url}/completions",
                        headers=headers,
                        json=request_data,
                        timeout=60.0
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Erro na API Mistral: {response.status_code} - {response.text}")
                        raise Exception(f"Erro na API: {response.status_code} - {response.text}")
                    
                    result = response.json()
                    return result["choices"][0]["text"]
                
                except Exception as e:
                    logger.error(f"Erro ao chamar API Mistral: {str(e)}")
                    raise
    
    async def _generate_stream(self, 
                          request_data: Dict[str, Any],
                          headers: Dict[str, str]) -> AsyncGenerator[str, None]:
        """
        Gera texto em formato de stream a partir da API Mistral.
        
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
                    f"{self.api_url}/completions",
                    headers=headers,
                    json=request_data,
                    timeout=120.0
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.text()
                        logger.error(f"Erro na API Mistral: {response.status_code} - {error_text}")
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
                                token = data["choices"][0].get("text", "")
                                if token:
                                    yield token
                        except json.JSONDecodeError:
                            logger.warning(f"Erro ao decodificar chunk JSON: {chunk}")
            
            except Exception as e:
                logger.error(f"Erro durante streaming da API Mistral: {str(e)}")
                raise
    
    async def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Cria embeddings para o texto usando a API Mistral.
        
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
            "model": self.model_config.get("embedding_model", "mistral-embed"),
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
                    logger.error(f"Erro na API Mistral: {response.status_code} - {response.text}")
                    raise Exception(f"Erro na API: {response.status_code} - {response.text}")
                
                result = response.json()
                embeddings = [item["embedding"] for item in result["data"]]
                
                # Retorna um único embedding ou uma lista dependendo da entrada
                return embeddings[0] if isinstance(text, str) else embeddings
            
            except Exception as e:
                logger.error(f"Erro ao obter embeddings da API Mistral: {str(e)}")
                raise