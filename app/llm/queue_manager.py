# app/llm/queue_manager.py
import asyncio
import time
import logging
import json
from typing import Dict, Any, Callable, Optional, Awaitable, List
import heapq
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import traceback
import psutil
import threading

# Configurar logging com formatação detalhada
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TaskMetrics:
    """Métricas detalhadas de uma tarefa."""
    task_id: str
    model_id: Optional[str]
    task_type: str
    priority: int
    enqueue_time: float
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    queue_wait_time: Optional[float] = None
    execution_time: Optional[float] = None
    status: str = "enqueued"  # enqueued, processing, completed, failed, timeout
    error: Optional[str] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None

class PriorityTask:
    """Tarefa com prioridade para a fila."""
    
    def __init__(self, priority: int, task_id: str, coro: Awaitable, 
                 timeout: Optional[float] = None, model_id: Optional[str] = None,
                 task_type: str = "generate", metadata: Optional[Dict] = None):
        self.priority = priority
        self.task_id = task_id
        self.coro = coro
        self.timeout = timeout
        self.timestamp = time.time()
        self.model_id = model_id
        self.task_type = task_type
        self.metadata = metadata or {}
        
        # Criar métricas iniciais
        self.metrics = TaskMetrics(
            task_id=task_id,
            model_id=model_id,
            task_type=task_type,
            priority=priority,
            enqueue_time=self.timestamp
        )
        
        logger.debug(f"📝 Nova tarefa criada: {task_id} | Tipo: {task_type} | "
                    f"Modelo: {model_id} | Prioridade: {priority} | "
                    f"Timeout: {timeout}s | Metadata: {metadata}")
        
    def __lt__(self, other):
        # Ordenar primeiro por prioridade (menor número = maior prioridade)
        # e depois por timestamp (mais antigo primeiro)
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

class LLMQueueManager:
    """
    Gerenciador de fila para solicitações LLM.
    Implementa priorização, limites de concorrência e timeouts.
    """
    
    def __init__(self, max_concurrent: int = 5, default_timeout: float = 500.0, 
                 log_interval: float = 30.0):
        self.tasks = []  # heap para prioridade
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.default_timeout = default_timeout
        self.log_interval = log_interval
        self.running = False
        self.worker_task = None
        self.stats_task = None
        
        # Estatísticas detalhadas
        self.model_stats = {}
        self.task_history: List[TaskMetrics] = []
        self.max_history_size = 1000
        
        # Contadores globais
        self.total_enqueued = 0
        self.total_completed = 0
        self.total_failed = 0
        self.total_timeouts = 0
        self.active_tasks = 0
        
        # Controle de recursos
        self.start_time = time.time()
        self.max_concurrent = max_concurrent
        
        logger.info(f"🚀 LLM Queue Manager inicializado | "
                   f"Max concurrent: {max_concurrent} | "
                   f"Default timeout: {default_timeout}s | "
                   f"Log interval: {log_interval}s")
    
    async def start(self):
        """Inicia o processamento da fila."""
        if self.running:
            logger.warning("⚠️ Queue Manager já está em execução")
            return
        
        self.running = True
        self.start_time = time.time()
        
        # Iniciar worker e task de estatísticas
        self.worker_task = asyncio.create_task(self._worker_loop())
        self.stats_task = asyncio.create_task(self._stats_loop())
        
        # Log inicial de sistema
        system_info = self._get_system_info()
        logger.info(f"✅ LLM Queue Manager iniciado | Sistema: {system_info}")
        
        # Log configurações
        logger.info(f"⚙️ Configurações: Max concurrent: {self.max_concurrent} | "
                   f"Default timeout: {self.default_timeout}s | "
                   f"Fila atual: {len(self.tasks)} tarefas")
    
    async def stop(self):
        """Para o processamento da fila."""
        if not self.running:
            logger.warning("⚠️ Queue Manager já está parado")
            return
        
        logger.info("🛑 Parando LLM Queue Manager...")
        
        self.running = False
        
        # Aguardar conclusão das tarefas
        if self.worker_task:
            await self.worker_task
            self.worker_task = None
            
        if self.stats_task:
            self.stats_task.cancel()
            try:
                await self.stats_task
            except asyncio.CancelledError:
                pass
            self.stats_task = None
        
        # Log final de estatísticas
        uptime = time.time() - self.start_time
        final_stats = self._get_session_stats()
        
        logger.info(f"✅ LLM Queue Manager parado | "
                   f"Uptime: {uptime:.2f}s | "
                   f"Stats finais: {final_stats}")
    
    async def enqueue(self, 
                      coro: Awaitable, 
                      priority: int = 5,
                      timeout: Optional[float] = None,
                      model_id: Optional[str] = None,
                      task_type: str = "generate",
                      metadata: Optional[Dict] = None) -> str:
        """
        Adiciona uma tarefa à fila.
        
        Args:
            coro: Coroutine a ser executada
            priority: Prioridade (1-10, menor número = maior prioridade)
            timeout: Timeout em segundos (None = usar padrão)
            model_id: ID do modelo LLM (para estatísticas)
            task_type: Tipo de tarefa (generate, embed, etc.)
            metadata: Metadados adicionais
            
        Returns:
            ID da tarefa
        """
        task_id = f"{int(time.time())}-{id(coro)}"
        current_queue_size = len(self.tasks)
        
        logger.debug(f"📥 Enfileirando tarefa {task_id} | "
                    f"Tipo: {task_type} | Modelo: {model_id} | "
                    f"Prioridade: {priority} | Fila atual: {current_queue_size}")
        
        task = PriorityTask(
            priority=priority,
            task_id=task_id,
            coro=coro,
            timeout=timeout or self.default_timeout,
            model_id=model_id,
            task_type=task_type,
            metadata=metadata
        )
        
        # Adicionar à heap
        heapq.heappush(self.tasks, task)
        self.total_enqueued += 1
        
        # Registrar para estatísticas do modelo
        if model_id:
            if model_id not in self.model_stats:
                self.model_stats[model_id] = {
                    "enqueued": 0,
                    "completed": 0,
                    "errors": 0,
                    "timeouts": 0,
                    "total_latency": 0.0,
                    "avg_latency": 0.0,
                    "min_latency": float('inf'),
                    "max_latency": 0.0,
                    "last_used": time.time()
                }
            self.model_stats[model_id]["enqueued"] += 1
            self.model_stats[model_id]["last_used"] = time.time()
        
        # Log de estado da fila após enqueue
        queue_stats = self._get_queue_stats()
        logger.info(f"➕ Tarefa {task_id} adicionada | "
                   f"Fila: {len(self.tasks)} | Ativas: {self.active_tasks} | "
                   f"Semáforo: {self.semaphore._value}/{self.max_concurrent} | "
                   f"Stats: {queue_stats}")
        
        return task_id
    
    async def _worker_loop(self):
        """Loop principal de processamento da fila."""
        logger.info("🔄 Worker loop iniciado")
        
        while self.running:
            if not self.tasks:
                # Fila vazia, aguardar
                await asyncio.sleep(0.1)
                continue
            
            # Obter próxima tarefa com maior prioridade
            task = heapq.heappop(self.tasks)
            
            # Verificar se já expirou na fila
            elapsed = time.time() - task.timestamp
            if elapsed > task.timeout:
                logger.warning(f"⏰ Tarefa {task.task_id} expirou na fila | "
                              f"Aguardou: {elapsed:.2f}s | Timeout: {task.timeout}s")
                
                task.metrics.status = "timeout"
                task.metrics.queue_wait_time = elapsed
                self._record_task_completion(task.metrics)
                self.total_timeouts += 1
                
                if task.model_id:
                    self.model_stats[task.model_id]["timeouts"] += 1
                continue
            
            # Executar tarefa com o semáforo (limitando concorrência)
            await self._execute_task(task)
        
        logger.info("🔄 Worker loop finalizado")
    
    async def _execute_task(self, task: PriorityTask):
        """Executa uma tarefa individual."""
        async with self.semaphore:
            self.active_tasks += 1
            task.metrics.start_time = time.time()
            task.metrics.queue_wait_time = task.metrics.start_time - task.metrics.enqueue_time
            task.metrics.status = "processing"
            
            # Log início da execução
            logger.info(f"🔥 Executando tarefa {task.task_id} | "
                       f"Aguardou na fila: {task.metrics.queue_wait_time:.2f}s | "
                       f"Semáforo: {self.max_concurrent - self.semaphore._value}/{self.max_concurrent}")
            
            # Capturar métricas de sistema antes da execução
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            initial_cpu = process.cpu_percent()
            
            try:
                # Configurar timeout restante
                elapsed = time.time() - task.timestamp
                remaining_timeout = max(0.5, task.timeout - elapsed)
                
                logger.debug(f"⏱️ Timeout restante para {task.task_id}: {remaining_timeout:.2f}s")
                
                # Executar a tarefa
                await asyncio.wait_for(task.coro, timeout=remaining_timeout)
                
                # Marcar como completada
                task.metrics.end_time = time.time()
                task.metrics.execution_time = task.metrics.end_time - task.metrics.start_time
                task.metrics.status = "completed"
                
                # Capturar métricas de sistema após execução
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                final_cpu = process.cpu_percent()
                
                task.metrics.memory_usage_mb = final_memory - initial_memory
                task.metrics.cpu_usage_percent = final_cpu
                
                # Log sucesso
                logger.info(f"✅ Tarefa {task.task_id} completada | "
                           f"Tempo execução: {task.metrics.execution_time:.2f}s | "
                           f"Tempo total: {task.metrics.end_time - task.metrics.enqueue_time:.2f}s | "
                           f"Memória: {task.metrics.memory_usage_mb:.2f}MB | "
                           f"CPU: {task.metrics.cpu_usage_percent:.1f}%")
                
                self.total_completed += 1
                
                # Atualizar estatísticas do modelo
                if task.model_id:
                    model_stats = self.model_stats[task.model_id]
                    model_stats["completed"] += 1
                    model_stats["total_latency"] += task.metrics.execution_time
                    model_stats["avg_latency"] = (
                        model_stats["total_latency"] / model_stats["completed"]
                    )
                    model_stats["min_latency"] = min(
                        model_stats["min_latency"], task.metrics.execution_time
                    )
                    model_stats["max_latency"] = max(
                        model_stats["max_latency"], task.metrics.execution_time
                    )
                    
                    logger.debug(f"📊 Stats do modelo {task.model_id}: "
                                f"Avg: {model_stats['avg_latency']:.2f}s | "
                                f"Min: {model_stats['min_latency']:.2f}s | "
                                f"Max: {model_stats['max_latency']:.2f}s")
                
            except asyncio.TimeoutError:
                task.metrics.end_time = time.time()
                task.metrics.execution_time = task.metrics.end_time - task.metrics.start_time
                task.metrics.status = "timeout"
                task.metrics.error = f"Timeout após {remaining_timeout:.2f}s"
                
                logger.error(f"⏰ Tarefa {task.task_id} excedeu timeout | "
                            f"Tempo execução: {task.metrics.execution_time:.2f}s | "
                            f"Timeout configurado: {task.timeout}s")
                
                self.total_timeouts += 1
                
                if task.model_id:
                    self.model_stats[task.model_id]["timeouts"] += 1
                
            except Exception as e:
                task.metrics.end_time = time.time()
                task.metrics.execution_time = task.metrics.end_time - task.metrics.start_time
                task.metrics.status = "failed"
                task.metrics.error = str(e)
                
                error_trace = traceback.format_exc()
                logger.error(f"❌ Erro na tarefa {task.task_id} | "
                            f"Erro: {str(e)} | "
                            f"Tempo execução: {task.metrics.execution_time:.2f}s | "
                            f"Trace: {error_trace}")
                
                self.total_failed += 1
                
                if task.model_id:
                    self.model_stats[task.model_id]["errors"] += 1
                
            finally:
                self.active_tasks -= 1
                self._record_task_completion(task.metrics)
                
                logger.debug(f"🔄 Tarefa {task.task_id} finalizada | "
                            f"Status: {task.metrics.status} | "
                            f"Tarefas ativas: {self.active_tasks}")
    
    async def _stats_loop(self):
        """Loop para logging periódico de estatísticas."""
        logger.info(f"📊 Stats loop iniciado (intervalo: {self.log_interval}s)")
        
        while self.running:
            try:
                await asyncio.sleep(self.log_interval)
                
                if self.running:  # Verificar novamente após sleep
                    uptime = time.time() - self.start_time
                    queue_stats = self._get_queue_stats()
                    session_stats = self._get_session_stats()
                    system_info = self._get_system_info()
                    
                    logger.info(f"📊 STATS PERIÓDICAS | "
                               f"Uptime: {uptime:.0f}s | "
                               f"Fila: {len(self.tasks)} | "
                               f"Ativas: {self.active_tasks} | "
                               f"Session: {session_stats} | "
                               f"Sistema: {system_info}")
                    
                    # Log detalhado de modelos
                    for model_id, stats in self.model_stats.items():
                        if stats["completed"] > 0:
                            logger.info(f"📊 Modelo {model_id}: "
                                       f"Completadas: {stats['completed']} | "
                                       f"Avg latency: {stats['avg_latency']:.2f}s | "
                                       f"Erros: {stats['errors']} | "
                                       f"Timeouts: {stats['timeouts']}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro no stats loop: {str(e)}")
        
        logger.info("📊 Stats loop finalizado")
    
    def _record_task_completion(self, metrics: TaskMetrics):
        """Registra a conclusão de uma tarefa no histórico."""
        self.task_history.append(metrics)
        
        # Manter tamanho máximo do histórico
        if len(self.task_history) > self.max_history_size:
            self.task_history = self.task_history[-self.max_history_size:]
    
    def _get_queue_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas atuais da fila."""
        return {
            "queue_size": len(self.tasks),
            "active_tasks": self.active_tasks,
            "available_slots": self.semaphore._value,
            "total_slots": self.max_concurrent
        }
    
    def _get_session_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas da sessão atual."""
        total_processed = self.total_completed + self.total_failed + self.total_timeouts
        
        return {
            "enqueued": self.total_enqueued,
            "completed": self.total_completed,
            "failed": self.total_failed,
            "timeouts": self.total_timeouts,
            "success_rate": f"{(self.total_completed / max(1, total_processed)) * 100:.1f}%"
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Obtém informações do sistema."""
        try:
            process = psutil.Process()
            return {
                "memory_mb": f"{process.memory_info().rss / 1024 / 1024:.1f}",
                "cpu_percent": f"{process.cpu_percent():.1f}%",
                "threads": threading.active_count()
            }
        except Exception:
            return {"error": "Unable to get system info"}
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas detalhadas para APIs ou debugging."""
        uptime = time.time() - self.start_time
        
        return {
            "uptime_seconds": uptime,
            "queue": self._get_queue_stats(),
            "session": self._get_session_stats(),
            "system": self._get_system_info(),
            "models": dict(self.model_stats),
            "recent_tasks": [
                asdict(task) for task in self.task_history[-10:]
            ]
        }
    
    def log_detailed_status(self):
        """Log completo do status atual para debugging."""
        stats = self.get_detailed_stats()
        
        logger.info(f"🔍 STATUS DETALHADO DO QUEUE MANAGER:")
        logger.info(f"   Uptime: {stats['uptime_seconds']:.2f}s")
        logger.info(f"   Fila: {json.dumps(stats['queue'], indent=2)}")
        logger.info(f"   Sessão: {json.dumps(stats['session'], indent=2)}")
        logger.info(f"   Sistema: {json.dumps(stats['system'], indent=2)}")
        
        if stats['models']:
            logger.info(f"   Modelos: {json.dumps(stats['models'], indent=2)}")
        
        if stats['recent_tasks']:
            logger.info(f"   Últimas tarefas: {json.dumps(stats['recent_tasks'], indent=2)}")

# Singleton para acesso global
_queue_manager = None

def get_llm_queue_manager() -> LLMQueueManager:
    """Obtém a instância do gerenciador de fila LLM."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = LLMQueueManager()
        logger.info("🆕 Nova instância do LLM Queue Manager criada")
    return _queue_manager