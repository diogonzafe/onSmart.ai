# app/core/sharded_cache.py

from __future__ import annotations
from typing import Dict, List, Any, Optional, Union
import logging
import redis.asyncio as redis
import json
import pickle
import hashlib

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.cache import Cache


logger = logging.getLogger(__name__)

class ShardedCache:
    """
    Cache distribuído com suporte a sharding.
    """
    
    def __init__(self, redis_urls: List[str], sharding_strategy: str = "tenant"):
        """
        Inicializa o cache shardado.
        
        Args:
            redis_urls: Lista de URLs de conexão Redis
            sharding_strategy: Estratégia de sharding ('tenant' ou 'key')
        """
        self.nodes = [redis.from_url(url, decode_responses=False) for url in redis_urls]
        self.strategy = sharding_strategy
        self.node_count = len(self.nodes)
        
        if self.node_count == 0:
            raise ValueError("Pelo menos um nó Redis é necessário")
        
        logger.info(f"Cache shardado inicializado com {self.node_count} nós")
    
    def get_shard(self, key: str, tenant_id: Optional[str] = None) -> redis.Redis:
        """
        Determina qual shard deve ser usado para uma chave.
        
        Args:
            key: Chave a ser armazenada
            tenant_id: ID do tenant (para estratégia 'tenant')
            
        Returns:
            Instância Redis do shard apropriado
        """
        if self.strategy == "tenant" and tenant_id:
            # Shard baseado no tenant_id
            shard_index = int(hashlib.md5(tenant_id.encode()).hexdigest(), 16) % self.node_count
        else:
            # Shard baseado na chave
            shard_index = int(hashlib.md5(key.encode()).hexdigest(), 16) % self.node_count
        
        return self.nodes[shard_index]
    
    async def get(self, key: str, tenant_id: Optional[str] = None) -> Any:
        """
        Obtém um valor do cache.
        
        Args:
            key: Chave do cache
            tenant_id: ID do tenant (opcional)
            
        Returns:
            Valor armazenado ou None se não encontrado
        """
        shard = self.get_shard(key, tenant_id)
        
        try:
            data = await shard.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Erro ao obter do cache: {str(e)}")
            return None
    
    async def set(self, 
               key: str, 
               value: Any, 
               ttl: int = 3600, 
               tenant_id: Optional[str] = None) -> bool:
        """
        Define um valor no cache.
        
        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl: Tempo de vida em segundos (padrão: 1 hora)
            tenant_id: ID do tenant (opcional)
            
        Returns:
            True se bem-sucedido, False caso contrário
        """
        shard = self.get_shard(key, tenant_id)
        
        try:
            # Serializar o valor usando pickle
            serialized = pickle.dumps(value)
            await shard.set(key, serialized, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Erro ao definir no cache: {str(e)}")
            return False
    
    async def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """
        Remove um valor do cache.
        
        Args:
            key: Chave do cache
            tenant_id: ID do tenant (opcional)
            
        Returns:
            True se bem-sucedido, False caso contrário
        """
        shard = self.get_shard(key, tenant_id)
        
        try:
            await shard.delete(key)
            return True
        except Exception as e:
            logger.error(f"Erro ao excluir do cache: {str(e)}")
            return False
    
    async def flush_tenant(self, tenant_id: str) -> bool:
        """
        Limpa todos os dados de um tenant específico.
        Isso requer uma convenção de nomenclatura de chaves.
        
        Args:
            tenant_id: ID do tenant
            
        Returns:
            True se bem-sucedido, False caso contrário
        """
        pattern = f"tenant:{tenant_id}:*"
        
        try:
            # Como não sabemos em qual shard estão as chaves, verificamos todas
            for shard in self.nodes:
                keys = await shard.keys(pattern)
                if keys:
                    await shard.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar tenant do cache: {str(e)}")
            return False

# Atualizar a função get_cache para suportar sharding
def get_cache(sharded: bool = False) -> Union[ShardedCache, 'Cache']:
    """
    Obtém a instância do cache.
    
    Args:
        sharded: Se deve usar cache shardado
        
    Returns:
        Instância do cache (shardado ou normal)
    """
    from app.config import settings
    
    if sharded:
        # Verificar se há múltiplos nós Redis configurados
        redis_urls = [settings.REDIS_URL]
        
        # Verificar se há URLs adicionais configuradas
        for i in range(1, 5):  # Suportar até 5 nós
            url_attr = f"REDIS_URL_{i}"
            if hasattr(settings, url_attr) and getattr(settings, url_attr):
                redis_urls.append(getattr(settings, url_attr))
        
        # Se tiver apenas um nó, não faz sentido usar sharding
        if len(redis_urls) == 1:
            # Obter a implementação original
            from app.core.cache import Cache
            return Cache(redis_urls[0])
        
        return ShardedCache(redis_urls)
    else:
        # Obter a implementação original
        from app.core.cache import Cache
        return Cache(settings.REDIS_URL)