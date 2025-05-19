# app/core/cache.py
import redis.asyncio as redis
from typing import Any, Optional, Dict, Union
import json
import pickle
import logging
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)

class Cache:
    """
    Implementação de cache usando Redis.
    """
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
        self._connect()
    
    def _connect(self):
        """Conecta ao Redis."""
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=False)
            logger.info(f"Conectado ao Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"Erro ao conectar ao Redis: {str(e)}")
            self.redis = None
    
    async def get(self, key: str) -> Any:
        """
        Obtém um valor do cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            Valor armazenado ou None se não encontrado
        """
        if not self.redis:
            return None
        
        try:
            data = await self.redis.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Erro ao obter do cache: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Define um valor no cache.
        
        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl: Tempo de vida em segundos (padrão: 1 hora)
            
        Returns:
            True se bem-sucedido, False caso contrário
        """
        if not self.redis:
            return False
        
        try:
            # Serializa o valor usando pickle para preservar tipos complexos
            serialized = pickle.dumps(value)
            await self.redis.set(key, serialized, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Erro ao definir no cache: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Remove um valor do cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            True se bem-sucedido, False caso contrário
        """
        if not self.redis:
            return False
        
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Erro ao excluir do cache: {str(e)}")
            return False
    
    async def flush(self) -> bool:
        """
        Limpa todo o cache.
        
        Returns:
            True se bem-sucedido, False caso contrário
        """
        if not self.redis:
            return False
        
        try:
            await self.redis.flushdb()
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar o cache: {str(e)}")
            return False

# Classe de cache simulado para testes sem Redis
class MockCache(Cache):
    """Cache simulado para testes."""
    
    def __init__(self):
        self.data = {}
        self.redis = None
        logger.info("Usando cache simulado para testes")
    
    async def get(self, key: str) -> Any:
        """Obtém um valor do cache simulado."""
        return self.data.get(key)
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Define um valor no cache simulado."""
        self.data[key] = value
        return True
    
    async def delete(self, key: str) -> bool:
        """Remove um valor do cache simulado."""
        if key in self.data:
            del self.data[key]
        return True
    
    async def flush(self) -> bool:
        """Limpa todo o cache simulado."""
        self.data.clear()
        return True

# Singleton para acesso global ao cache
@lru_cache()
def get_cache() -> Cache:
    """
    Obtém a instância do cache.
    
    Returns:
        Instância do cache (real ou simulado)
    """
    if hasattr(settings, "REDIS_URL") and settings.REDIS_URL:
        return Cache(settings.REDIS_URL)
    else:
        logger.warning("REDIS_URL não configurado. Usando cache simulado para testes.")
        return MockCache()