# app/core/advanced_monitoring.py
import time
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)

class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class PerformanceMetric:
    """Métrica de performance individual."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class Alert:
    """Alerta do sistema."""
    id: str
    level: AlertLevel
    title: str
    message: str
    component: str
    timestamp: datetime
    resolved: bool = False
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['level'] = self.level.value
        return result

class AdvancedMonitoring:
    """
    Sistema de monitoramento avançado para o sistema multi-agentes.
    Coleta métricas, detecta anomalias e gera alertas.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Inicializa o sistema de monitoramento.
        
        Args:
            redis_url: URL de conexão do Redis (opcional)
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis: Optional[redis.Redis] = None
        self._connect()
        
        # Armazenamento local para métricas recentes
        self.local_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alerts: Dict[str, Alert] = {}
        
        # Configurações de thresholds
        self.thresholds = {
            "response_time": {"warning": 5.0, "critical": 10.0},
            "error_rate": {"warning": 0.05, "critical": 0.1},
            "queue_size": {"warning": 100, "critical": 500},
            "memory_usage": {"warning": 0.8, "critical": 0.9},
            "active_conversations": {"warning": 1000, "critical": 5000}
        }
        
        # Detectores de anomalias
        self.anomaly_detectors = {}
        
        logger.info("Sistema de monitoramento avançado inicializado")
    
    def _connect(self) -> None:
        """Conecta ao Redis."""
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"Monitoramento conectado ao Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"Erro ao conectar ao Redis para monitoramento: {str(e)}")
            self.redis = None
    
    async def record_metric(
        self, 
        name: str, 
        value: float, 
        unit: str = "count",
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Registra uma métrica.
        
        Args:
            name: Nome da métrica
            value: Valor da métrica
            unit: Unidade de medida
            tags: Tags adicionais
        """
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        
        # Armazenar localmente
        self.local_metrics[name].append(metric)
        
        # Persistir no Redis se disponível
        if self.redis:
            try:
                key = f"monitoring:metric:{name}"
                await self.redis.lpush(key, json.dumps(metric.to_dict()))
                await self.redis.ltrim(key, 0, 999)  # Manter apenas os últimos 1000
                await self.redis.expire(key, 86400)  # Expirar após 24 horas
            except Exception as e:
                logger.error(f"Erro ao persistir métrica no Redis: {str(e)}")
        
        # Verificar thresholds e gerar alertas
        await self._check_thresholds(name, value, tags)
    
    async def _check_thresholds(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]]
    ) -> None:
        """
        Verifica thresholds e gera alertas se necessário.
        
        Args:
            metric_name: Nome da métrica
            value: Valor da métrica
            tags: Tags da métrica
        """
        if metric_name not in self.thresholds:
            return
        
        thresholds = self.thresholds[metric_name]
        alert_level = None
        
        if value >= thresholds.get("critical", float('inf')):
            alert_level = AlertLevel.CRITICAL
        elif value >= thresholds.get("warning", float('inf')):
            alert_level = AlertLevel.WARNING
        
        if alert_level:
            await self._create_alert(
                level=alert_level,
                title=f"{metric_name.title()} threshold exceeded",
                message=f"{metric_name} value {value} exceeded {alert_level.value} threshold",
                component=metric_name,
                metadata={"value": value, "tags": tags}
            )
    
    async def _create_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        component: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Cria um novo alerta.
        
        Args:
            level: Nível do alerta
            title: Título do alerta
            message: Mensagem do alerta
            component: Componente que gerou o alerta
            metadata: Metadados adicionais
            
        Returns:
            ID do alerta criado
        """
        alert_id = f"{component}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            level=level,
            title=title,
            message=message,
            component=component,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        # Armazenar localmente
        self.alerts[alert_id] = alert
        
        # Persistir no Redis
        if self.redis:
            try:
                key = f"monitoring:alert:{alert_id}"
                await self.redis.setex(key, 86400, json.dumps(alert.to_dict()))
                
                # Adicionar à lista de alertas ativos
                await self.redis.lpush("monitoring:alerts:active", alert_id)
                await self.redis.ltrim("monitoring:alerts:active", 0, 999)
            except Exception as e:
                logger.error(f"Erro ao persistir alerta no Redis: {str(e)}")
        
        # Log do alerta
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }.get(level, logging.INFO)
        
        logger.log(log_level, f"ALERT [{level.value.upper()}] {title}: {message}")
        
        return alert_id
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve um alerta.
        
        Args:
            alert_id: ID do alerta
            
        Returns:
            True se resolvido com sucesso
        """
        if alert_id in self.alerts:
            self.alerts[alert_id].resolved = True
            
            # Atualizar no Redis
            if self.redis:
                try:
                    key = f"monitoring:alert:{alert_id}"
                    await self.redis.setex(key, 86400, json.dumps(self.alerts[alert_id].to_dict()))
                    
                    # Remover da lista de alertas ativos
                    await self.redis.lrem("monitoring:alerts:active", 1, alert_id)
                except Exception as e:
                    logger.error(f"Erro ao atualizar alerta no Redis: {str(e)}")
            
            logger.info(f"Alerta {alert_id} resolvido")
            return True
        
        return False
    
    async def get_metrics_summary(
        self, 
        time_range: str = "1h",
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Obtém um resumo das métricas.
        
        Args:
            time_range: Período de tempo ('1h', '24h', '7d')
            metrics: Lista de métricas específicas (opcional)
            
        Returns:
            Resumo das métricas
        """
        # Calcular timestamp de corte
        now = datetime.utcnow()
        time_delta = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7)
        }.get(time_range, timedelta(hours=1))
        
        cutoff_time = now - time_delta
        
        summary = {}
        
        # Processar métricas locais
        for metric_name, metric_deque in self.local_metrics.items():
            if metrics and metric_name not in metrics:
                continue
            
            # Filtrar por tempo
            recent_metrics = [
                m for m in metric_deque 
                if m.timestamp >= cutoff_time
            ]
            
            if recent_metrics:
                values = [m.value for m in recent_metrics]
                summary[metric_name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "latest": values[-1],
                    "unit": recent_metrics[-1].unit
                }
        
        return summary
    
    async def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Dict[str, Any]]:
        """
        Obtém alertas ativos.
        
        Args:
            level: Filtrar por nível (opcional)
            
        Returns:
            Lista de alertas ativos
        """
        active_alerts = []
        
        for alert in self.alerts.values():
            if alert.resolved:
                continue
                
            if level and alert.level != level:
                continue
            
            active_alerts.append(alert.to_dict())
        
        # Ordenar por timestamp (mais recentes primeiro)
        active_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return active_alerts
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica a saúde geral do sistema.
        
        Returns:
            Status de saúde do sistema
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
            "alerts": {
                "critical": 0,
                "warning": 0,
                "total": 0
            }
        }
        
        # Verificar componentes
        components = ["redis", "database", "llm_router", "agents"]
        
        for component in components:
            health_status["components"][component] = await self._check_component_health(component)
        
        # Contar alertas
        for alert in self.alerts.values():
            if not alert.resolved:
                health_status["alerts"]["total"] += 1
                if alert.level == AlertLevel.CRITICAL:
                    health_status["alerts"]["critical"] += 1
                elif alert.level == AlertLevel.WARNING:
                    health_status["alerts"]["warning"] += 1
        
        # Determinar status geral
        if health_status["alerts"]["critical"] > 0:
            health_status["status"] = "critical"
        elif health_status["alerts"]["warning"] > 0:
            health_status["status"] = "warning"
        elif any(comp["status"] != "healthy" for comp in health_status["components"].values()):
            health_status["status"] = "degraded"
        
        return health_status
    
    async def _check_component_health(self, component: str) -> Dict[str, Any]:
        """
        Verifica a saúde de um componente específico.
        
        Args:
            component: Nome do componente
            
        Returns:
            Status do componente
        """
        try:
            if component == "redis":
                if self.redis:
                    await self.redis.ping()
                    return {"status": "healthy", "message": "Redis responding"}
                else:
                    return {"status": "unhealthy", "message": "Redis not connected"}
            
            elif component == "database":
                # Implementar verificação do banco de dados
                return {"status": "healthy", "message": "Database accessible"}
            
            elif component == "llm_router":
                # Implementar verificação do roteador LLM
                return {"status": "healthy", "message": "LLM router operational"}
            
            elif component == "agents":
                # Implementar verificação dos agentes
                return {"status": "healthy", "message": "Agents system operational"}
            
            else:
                return {"status": "unknown", "message": f"Unknown component: {component}"}
                
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}

# Decorador para monitoramento automático
def monitor_performance(metric_name: str, unit: str = "seconds"):
    """
    Decorador para monitorar automaticamente a performance de funções.
    
    Args:
        metric_name: Nome da métrica
        unit: Unidade de medida
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                success = True
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                monitoring = get_advanced_monitoring()
                
                # Registrar métrica de tempo
                await monitoring.record_metric(
                    name=f"{metric_name}_duration",
                    value=execution_time,
                    unit=unit,
                    tags={"function": func.__name__, "success": str(success)}
                )
                
                # Registrar métrica de sucesso/falha
                await monitoring.record_metric(
                    name=f"{metric_name}_calls",
                    value=1,
                    unit="count",
                    tags={"function": func.__name__, "success": str(success)}
                )
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                success = True
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                # Para funções síncronas, usar asyncio.create_task se estivermos em um loop
                try:
                    monitoring = get_advanced_monitoring()
                    asyncio.create_task(monitoring.record_metric(
                        name=f"{metric_name}_duration",
                        value=execution_time,
                        unit=unit,
                        tags={"function": func.__name__, "success": str(success)}
                    ))
                except RuntimeError:
                    # Não há loop ativo - apenas log
                    logger.debug(f"Performance: {func.__name__} took {execution_time:.3f}s")
            
            return result
        
        # Escolher wrapper baseado no tipo de função
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Singleton para acesso global
_advanced_monitoring_instance = None

def get_advanced_monitoring() -> AdvancedMonitoring:
    """
    Obtém a instância do sistema de monitoramento avançado.
    
    Returns:
        Instância do AdvancedMonitoring
    """
    global _advanced_monitoring_instance
    
    if _advanced_monitoring_instance is None:
        _advanced_monitoring_instance = AdvancedMonitoring()
    
    return _advanced_monitoring_instance