# app/llm/llama.py
import os
import json
from typing import Dict, List, Any, Optional, Union, AsyncGenerator
import logging
import asyncio
from llama_cpp import Llama
from llama_cpp.llama_tokenizer import LlamaTokenizer

from app.llm.base import LLMBase
from app.config import settings

logger = logging.getLogger(__name__)

class LlamaLLM(LLMBase):
    """
    Implementação de LLM para modelos Llama usando llama.cpp.
    """
    
    def initialize(self) -> None:
        """Inicializa o modelo Llama."""
        model_path = self.model_config.get("model_path")
        
        if not model_path:
            raise ValueError("model_path deve ser especificado para LlamaLLM")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Arquivo do modelo não encontrado: {model_path}")
        
        # Configurações padrão com fallback para configurações customizadas
        n_ctx = self.model_config.get("n_ctx", 4096)
        n_gpu_layers = self.model_config.get("n_gpu_layers", -1)  # -1 para usar todas
        
        try:
            self.model = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=self.model_config.get("verbose", False)
            )
            self.tokenizer = LlamaTokenizer(self.model)
            logger.info(f"Modelo Llama inicializado: {model_path}")
        except Exception as e:
            logger.error(f"Erro ao inicializar modelo Llama: {str(e)}")
            raise
    
    async def generate(self, 
                  prompt: str, 
                  max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None,
                  stream: bool = False,
                  **kwargs) -> Union[str, AsyncGenerator[str, None]]:
        """
        Gera texto usando o modelo Llama.
        
        Args:
            prompt: Texto de entrada
            max_tokens: Número máximo de tokens (padrão: 256)
            temperature: Controle de aleatoriedade (padrão: 0.7)
            stream: Se True, retorna um gerador para streaming
        
        Returns:
            Texto gerado ou gerador de streaming
        """
        max_tokens = max_tokens or self.model_config.get("max_tokens", 256)
        temperature = temperature or self.model_config.get("temperature", 0.7)
        
        if stream:
            return self._generate_stream(prompt, max_tokens, temperature, **kwargs)
        else:
            # Executar em um thread separado para não bloquear o loop de eventos
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.model.generate(
                    self.tokenizer.encode(prompt),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
            )
            generated_text = self.tokenizer.decode(result)
            return generated_text
    
    async def _generate_stream(self, 
                          prompt: str, 
                          max_tokens: int,
                          temperature: float,
                          **kwargs) -> AsyncGenerator[str, None]:
        """
        Gera texto em formato de stream.
        
        Args:
            prompt: Texto de entrada
            max_tokens: Número máximo de tokens
            temperature: Controle de aleatoriedade
        
        Yields:
            Pedaços de texto gerados
        """
        prompt_tokens = self.tokenizer.encode(prompt)
        
        try:
            async for token in self._token_generator(prompt_tokens, max_tokens, temperature, **kwargs):
                yield self.tokenizer.decode([token])
        except Exception as e:
            logger.error(f"Erro durante streaming do Llama: {str(e)}")
            raise
    
    async def _token_generator(self, 
                          prompt_tokens: List[int], 
                          max_tokens: int,
                          temperature: float,
                          **kwargs) -> AsyncGenerator[int, None]:
        """
        Gerador de tokens individuais para streaming.
        
        Args:
            prompt_tokens: Tokens de entrada
            max_tokens: Número máximo de tokens a gerar
            temperature: Controle de aleatoriedade
        
        Yields:
            Tokens individuais
        """
        # Inicializa o contexto com os tokens do prompt
        loop = asyncio.get_event_loop()
        
        self.model.reset()
        await loop.run_in_executor(
            None,
            lambda: self.model.eval(prompt_tokens)
        )
        
        # Gera tokens um por um
        for i in range(max_tokens):
            token = await loop.run_in_executor(
                None,
                lambda: self.model.sample(temperature=temperature, **kwargs)
            )
            
            yield token
            
            # Avalia o token para atualizar o estado do modelo
            await loop.run_in_executor(
                None,
                lambda: self.model.eval([token])
            )
            
            # Se for token de fim de sequência, pare
            if token == self.tokenizer.eos_token_id:
                break
    
    async def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Cria embeddings para o texto usando o modelo Llama.
        
        Args:
            text: Texto ou lista de textos
            
        Returns:
            Vetor de embedding ou lista de vetores
        """
        # Verificar se estamos lidando com uma string única ou uma lista
        if isinstance(text, str):
            texts = [text]
        else:
            texts = text
        
        embeddings = []
        for single_text in texts:
            # Executar em um thread separado para não bloquear
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: self.model.embed(single_text)
            )
            embeddings.append(embedding.tolist())  # Converter numpy array para lista
        
        # Retornar um único embedding ou lista dependendo da entrada
        return embeddings[0] if isinstance(text, str) else embeddings