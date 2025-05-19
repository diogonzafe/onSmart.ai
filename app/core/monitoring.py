# app/core/monitoring.py
import time
import logging
import uuid
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable
import asyncio
from functools import wraps
from redis.asyncio import Redis
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)

class LLMMetrics:
    """
    Sistema de monitoramento avançado para LLMs.
    Rastreia métricas de desempenho e uso de modelos LLM.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Inicializa o sistema de métricas.
        
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
            logger.info(f"Sistema de métricas conectado ao Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"Erro ao conectar ao Redis para métricas: {str(e)}")
            self.redis = None
    
    async def record_request(
        self,
        model_id: str,
        operation: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Registra o início de uma solicitação LLM.
        
        Args:
            model_id: ID do modelo utilizado
            operation: Tipo de operação ('generate' ou 'embed')
            user_id: ID do usuário (opcional)
            metadata: Metadados adicionais (opcional)
            
        Returns:
            ID único da solicitação para rastreamento
        """
        request_id = str(uuid.uuid4())
        timestamp = time.time()
        
        data = {
            "request_id": request_id,
            "model_id": model_id,
            "operation": operation,
            "user_id": user_id or "anonymous",
            "status": "started",
            "start_time": timestamp,
            "metadata": metadata or {}
        }
        
        if self.redis:
            try:
                # Armazenar dados da solicitação
                key = f"llm_metrics:request:{request_id}"
                await self.redis.hmset(key, {
                    "data": json.dumps(data),
                    "created_at": timestamp
                })
                await self.redis.expire(key, 86400)  # Expirar após 24 horas
                
                # Incrementar contadores
                day_key = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
                await self.redis.hincrby(f"llm_metrics:daily:{day_key}", f"{model_id}:{operation}:requests", 1)
                
            except Exception as e:
                logger.error(f"Erro ao registrar início da solicitação: {str(e)}")
        
        return request_id
    
    async def record_response(
        self,
        request_id: str,
        success: bool,
        latency: float,
        tokens: Optional[int] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Registra o resultado de uma solicitação LLM.
        
        Args:
            request_id: ID da solicitação
            success: Se a solicitação foi bem-sucedida
            latency: Tempo de resposta em segundos
            tokens: Número de tokens processados (opcional)
            error: Mensagem de erro, se houver (opcional)
            metadata: Metadados adicionais (opcional)
        """
        if not self.redis:
            return
        
        try:
            # Obter dados da solicitação
            key = f"llm_metrics:request:{request_id}"
            request_data = await self.redis.hget(key, "data")
            
            if not request_data:
                logger.warning(f"Solicitação não encontrada para ID {request_id}")
                return
            
            data = json.loads(request_data)
            
            # Atualizar com informações da resposta
            data.update({
                "status": "completed" if success else "failed",
                "end_time": time.time(),
                "latency": latency,
                "tokens": tokens,
                "error": error,
                "response_metadata": metadata or {}
            })
            
            # Atualizar no Redis
            await self.redis.hset(key, "data", json.dumps(data))
            
            # Atualizar métricas agregadas
            day_key = datetime.utcfromtimestamp(data["start_time"]).strftime("%Y-%m-%d")
            model_id = data["model_id"]
            operation = data["operation"]
            
            async with self.redis.pipeline() as pipe:
                # Incrementar contadores de sucesso/falha
                status_key = "successes" if success else "failures"
                await pipe.hincrby(f"llm_metrics:daily:{day_key}", f"{model_id}:{operation}:{status_key}", 1)
                
                # Adicionar à lista de latências
                await pipe.lpush(
                    f"llm_metrics:latency:{model_id}:{operation}:{day_key}", 
                    latency
                )
                # Limitar a lista de latências para evitar crescimento excessivo
                await pipe.ltrim(
                    f"llm_metrics:latency:{model_id}:{operation}:{day_key}",
                    0, 999
                )
                
                # Se houver tokens, atualizar contadores
                if tokens:
                    await pipe.hincrby(
                        f"llm_metrics:daily:{day_key}", 
                        f"{model_id}:{operation}:tokens", 
                        tokens
                    )
                
                await pipe.execute()
                
        except Exception as e:
            logger.error(f"Erro ao registrar resposta da solicitação: {str(e)}")
    
    async def get_model_metrics(
        self, 
        model_id: Optional[str] = None,
        operation: Optional[str] = None,
        period: str = "today"
    ) -> Dict[str, Any]:
        """
        Obtém métricas agregadas para um modelo específico.
        
        Args:
            model_id: ID do modelo (opcional, para todos os modelos)
            operation: Tipo de operação (opcional, para todas as operações)
            period: Período ('today', 'yesterday', 'week', 'month')
            
        Returns:
            Dicionário com métricas agregadas
        """
        if not self.redis:
            return {"error": "Redis não disponível para métricas"}
        
        try:
            # Determinar datas para o período solicitado
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            if period == "today":
                dates = [today]
            elif period == "yesterday":
                yesterday = (datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                dates = [yesterday]
            elif period == "week":
                dates = [
                    (datetime.utcnow() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(7)
                ]
            elif period == "month":
                dates = [
                    (datetime.utcnow() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(30)
                ]
            else:
                dates = [today]
            
            # Coletar métricas para todas as datas no período
            all_metrics = {}
            
            for date in dates:
                day_key = f"llm_metrics:daily:{date}"
                day_data = await self.redis.hgetall(day_key)
                
                if not day_data:
                    continue
                
                # Processar dados do dia
                for key, value in day_data.items():
                    parts = key.split(":")
                    
                    # Verificar se corresponde aos filtros
                    if len(parts) < 3:
                        continue
                        
                    current_model = parts[0]
                    current_op = parts[1]
                    metric_type = parts[2]
                    
                    if model_id and current_model != model_id:
                        continue
                        
                    if operation and current_op != operation:
                        continue
                    
                    # Adicionar ao dicionário de métricas
                    model_key = current_model
                    if model_key not in all_metrics:
                        all_metrics[model_key] = {}
                    
                    op_key = current_op
                    if op_key not in all_metrics[model_key]:
                        all_metrics[model_key][op_key] = {
                            "requests": 0,
                            "successes": 0,
                            "failures": 0,
                            "tokens": 0,
                            "latency_avg": 0,
                            "latency_p95": 0,
                            "latency_p99": 0,
                            "success_rate": 0
                        }
                    
                    # Atualizar contadores
                    if metric_type in ["requests", "successes", "failures", "tokens"]:
                        all_metrics[model_key][op_key][metric_type] += int(value)
                
                # Processar latências
                for model_key in all_metrics:
                    for op_key in all_metrics[model_key]:
                        # Obter lista de latências
                        latency_key = f"llm_metrics:latency:{model_key}:{op_key}:{date}"
                        latencies = await self.redis.lrange(latency_key, 0, -1)
                        
                        if latencies:
                            # Converter para números
                            latencies = [float(l) for l in latencies]
                            
                            # Calcular métricas
                            all_metrics[model_key][op_key]["latency_avg"] = sum(latencies) / len(latencies)
                            
                            # Percentis
                            sorted_latencies = sorted(latencies)
                            p95_idx = int(len(sorted_latencies) * 0.95)
                            p99_idx = int(len(sorted_latencies) * 0.99)
                            
                            all_metrics[model_key][op_key]["latency_p95"] = sorted_latencies[p95_idx] if len(sorted_latencies) > p95_idx else 0
                            all_metrics[model_key][op_key]["latency_p99"] = sorted_latencies[p99_idx] if len(sorted_latencies) > p99_idx else 0
                            
                            # Taxa de sucesso
                            requests = all_metrics[model_key][op_key]["requests"]
                            successes = all_metrics[model_key][op_key]["successes"]
                            
                            if requests > 0:
                                all_metrics[model_key][op_key]["success_rate"] = (successes / requests) * 100
            
            return all_metrics
            
        except Exception as e:
            logger.error(f"Erro ao obter métricas do modelo: {str(e)}")
            return {"error": str(e)}
    
    async def get_request_details(self, request_id: str) -> Dict[str, Any]:
        """
        Obtém detalhes de uma solicitação específica.
        
        Args:
            request_id: ID da solicitação
            
        Returns:
            Detalhes da solicitação ou dicionário vazio se não encontrada
        """
        if not self.redis:
            return {}
        
        try:
            key = f"llm_metrics:request:{request_id}"
            data = await self.redis.hget(key, "data")
            
            if data:
                return json.loads(data)
            
            return {}
            
        except Exception as e:
            logger.error(f"Erro ao obter detalhes da solicitação: {str(e)}")
            return {}

# Decorator para monitorar operações LLM
def monitor_llm(func=None, *, operation: str = None):
    """
    Decorator para monitorar operações LLM automaticamente.
    
    Args:
        func: Função a ser decorada
        operation: Tipo de operação ('generate' ou 'embed')
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extrair model_id dos argumentos (assumindo que a função pertence a uma classe LLM)
            if args and hasattr(args[0], 'model_name'):
                model_id = args[0].model_name
            else:
                model_id = kwargs.get('model_id', 'unknown')
            
            # Determinar operação com base no nome da função ou parâmetro
            op = operation or func.__name__
            
            # Obter o sistema de métricas
            metrics = get_llm_metrics()
            
            # Registrar início da solicitação
            request_id = await metrics.record_request(
                model_id=model_id,
                operation=op,
                metadata={
                    "args": str(args[1:] if args else []),  # Excluir self em métodos de classe
                    "kwargs": str({k: v for k, v in kwargs.items() if k not in ['api_key']})  # Excluir chaves sensíveis
                }
            )
            
            start_time = time.time()
            success = False
            error_msg = None
            result = None
            tokens = None
            
            try:
                # Chamar a função original
                result = await func(*args, **kwargs)
                success = True
                
                # Estimar o número de tokens (isso é aproximado e pode precisar ser ajustado)
                if op == 'generate' and isinstance(result, str):
                    # Aproximação simples: ~1.3 tokens por palavra
                    tokens = int(len(result.split()) * 1.3)
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                raise
                
            finally:
                # Registrar resultado, independente de sucesso ou falha
                await metrics.record_response(
                    request_id=request_id,
                    success=success,
                    latency=time.time() - start_time,
                    tokens=tokens,
                    error=error_msg,
                    metadata={
                        "result_type": type(result).__name__ if result is not None else None
                    }
                )
        
        return wrapper
    
    # Permitir uso como @monitor_llm ou @monitor_llm(operation='generate')
    if func is None:
        return decorator
    return decorator(func)

# Singleton para acesso global às métricas
_llm_metrics_instance = None

def get_llm_metrics() -> LLMMetrics:
    """
    Obtém a instância do sistema de métricas.
    
    Returns:
        Instância do LLMMetrics
    """
    global _llm_metrics_instance
    
    if _llm_metrics_instance is None:
        _llm_metrics_instance = LLMMetrics()
    
    return _llm_metrics_instance