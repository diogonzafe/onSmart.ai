# app/core/rate_limiter.py
import time
import logging
import asyncio
from typing import Dict, Optional, Tuple, Union
from redis.asyncio import Redis
import redis.asyncio as redis
from app.config import settings
from app.core.cache import get_cache

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Implementação de limitação de taxa usando Redis.
    Limita o número de solicitações por usuário/chave em períodos definidos.
    
    Implementa uma variação do algoritmo "token bucket" para permitir rajadas controladas.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Inicializa o limitador de taxa.
        
        Args:
            redis_url: URL de conexão do Redis (opcional)
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis: Optional[Redis] = None
        self._connect()
    
    def _connect(self) -> None:
        """Conecta ao Redis."""
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"Rate Limiter conectado ao Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"Erro ao conectar ao Redis para rate limiter: {str(e)}")
            self.redis = None
    
    async def check_rate_limit(
        self, 
        key: str, 
        limit: int = 10, 
        period: int = 60,
        category: str = "default"
    ) -> Tuple[bool, Dict[str, Union[int, float]]]:
        """
        Verifica se uma solicitação pode ser processada com base nas limitações de taxa.
        
        Args:
            key: Identificador único (por exemplo, user_id ou IP)
            limit: Número máximo de solicitações permitidas no período
            period: Período em segundos (padrão: 60 segundos)
            category: Categoria da solicitação (ex: "generate", "embed")
            
        Returns:
            Tupla com (is_allowed, rate_limit_info)
            - is_allowed: True se a solicitação for permitida
            - rate_limit_info: Dicionário com informações sobre o limite de taxa
        """
        if not self.redis:
            # Se o Redis não estiver disponível, permitimos a solicitação
            logger.warning("Redis não disponível para verificação de rate limit")
            return True, {"remaining": 999, "reset": time.time() + period}
        
        # Construir a chave do Redis
        redis_key = f"rate_limit:{category}:{key}"
        
        # Timestamp atual
        now = time.time()
        
        try:
            # Pipeline para operações atômicas
            async with self.redis.pipeline() as pipe:
                # Obter o contador atual e o timestamp
                await pipe.hmget(redis_key, "count", "reset_at")
                # Adicionar as operações para incrementar o contador
                await pipe.hincrby(redis_key, "count", 1)
                await pipe.expire(redis_key, period)
                
                # Executar as operações
                results = await pipe.execute()
                
                # Extrair o contador e o timestamp
                current_count = results[0][0]
                reset_at = results[0][1]
                
                # Se não existir contador ou o timestamp expirou, reiniciar
                if not current_count or not reset_at or float(reset_at) < now:
                    # Definir novo timestamp de expiração
                    reset_at = now + period
                    
                    # Reiniciar contador
                    await self.redis.hmset(redis_key, {
                        "count": 1, 
                        "reset_at": reset_at
                    })
                    
                    # Definir tempo de expiração na chave
                    await self.redis.expire(redis_key, period)
                    
                    # Limitação de taxa não ultrapassada
                    return True, {"remaining": limit - 1, "reset": reset_at}
                
                # Converter strings para valores apropriados
                current_count = int(current_count)
                reset_at = float(reset_at)
                
                # Verificar se o limite foi atingido
                is_allowed = current_count <= limit
                remaining = max(0, limit - current_count)
                
                # Registrar informações sobre limitação de taxa
                if not is_allowed:
                    logger.warning(
                        f"Rate limit atingido para {key} em {category}. "
                        f"Limite: {limit}, Atual: {current_count}, "
                        f"Reset em: {int(reset_at - now)}s"
                    )
                
                return is_allowed, {"remaining": remaining, "reset": reset_at}
                
        except Exception as e:
            logger.error(f"Erro ao verificar rate limit: {str(e)}")
            # Em caso de erro, permitimos a solicitação
            return True, {"remaining": 999, "reset": time.time() + period}
    
    async def get_current_usage(self, key: str, category: str = "default") -> Dict[str, Union[int, float]]:
        """
        Obtém informações sobre o uso atual do rate limit.
        
        Args:
            key: Identificador único
            category: Categoria da solicitação
            
        Returns:
            Dicionário com informações sobre o uso atual
        """
        if not self.redis:
            return {"count": 0, "remaining": 999, "reset": time.time() + 60}
        
        redis_key = f"rate_limit:{category}:{key}"
        
        try:
            data = await self.redis.hgetall(redis_key)
            
            if not data:
                return {"count": 0, "remaining": 999, "reset": time.time() + 60}
            
            count = int(data.get("count", 0))
            reset_at = float(data.get("reset_at", time.time() + 60))
            
            # Calculamos o valor padrão de limit com base no limit default
            # Este valor é apenas uma estimativa, já que o limite real pode variar por solicitação
            default_limit = 10
            remaining = max(0, default_limit - count)
            
            return {
                "count": count,
                "remaining": remaining,
                "reset": reset_at
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter usage de rate limit: {str(e)}")
            return {"count": 0, "remaining": 999, "reset": time.time() + 60}
    
    async def reset_rate_limit(self, key: str, category: str = "default") -> bool:
        """
        Reseta o contador de rate limit para uma chave específica.
        
        Args:
            key: Identificador único
            category: Categoria da solicitação
            
        Returns:
            True se o reset foi bem-sucedido
        """
        if not self.redis:
            return False
        
        redis_key = f"rate_limit:{category}:{key}"
        
        try:
            await self.redis.delete(redis_key)
            return True
        except Exception as e:
            logger.error(f"Erro ao resetar rate limit: {str(e)}")
            return False

# Singleton para acesso global ao rate limiter
_rate_limiter_instance = None

def get_rate_limiter() -> RateLimiter:
    """
    Obtém a instância do rate limiter.
    
    Returns:
        Instância do RateLimiter
    """
    global _rate_limiter_instance
    
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    
    return _rate_limiter_instance