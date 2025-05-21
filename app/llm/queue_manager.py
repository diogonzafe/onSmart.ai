# app/llm/queue_manager.py
import asyncio
import time
import logging
from typing import Dict, Any, Callable, Optional, Awaitable
import heapq

logger = logging.getLogger(__name__)

class PriorityTask:
    """Tarefa com prioridade para a fila."""
    
    def __init__(self, priority: int, task_id: str, coro: Awaitable, timeout: Optional[float] = None):
        self.priority = priority
        self.task_id = task_id
        self.coro = coro
        self.timeout = timeout
        self.timestamp = time.time()
        
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
    
    def __init__(self, max_concurrent: int = 5, default_timeout: float = 60.0):
        self.tasks = []  # heap para prioridade
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.default_timeout = default_timeout
        self.running = False
        self.worker_task = None
        self.model_stats = {}
        
    async def start(self):
        """Inicia o processamento da fila."""
        if self.running:
            return
        
        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("LLM Queue Manager iniciado")
    
    async def stop(self):
        """Para o processamento da fila."""
        if not self.running:
            return
        
        self.running = False
        if self.worker_task:
            await self.worker_task
            self.worker_task = None
        
        logger.info("LLM Queue Manager parado")
    
    async def enqueue(self, 
                      coro: Awaitable, 
                      priority: int = 5,
                      timeout: Optional[float] = None,
                      model_id: Optional[str] = None,
                      task_type: str = "generate") -> str:
        """
        Adiciona uma tarefa à fila.
        
        Args:
            coro: Coroutine a ser executada
            priority: Prioridade (1-10, menor número = maior prioridade)
            timeout: Timeout em segundos (None = usar padrão)
            model_id: ID do modelo LLM (para estatísticas)
            task_type: Tipo de tarefa (generate, embed, etc.)
            
        Returns:
            ID da tarefa
        """
        task_id = f"{int(time.time())}-{id(coro)}"
        task = PriorityTask(
            priority=priority,
            task_id=task_id,
            coro=coro,
            timeout=timeout or self.default_timeout
        )
        
        # Adicionar à heap
        heapq.heappush(self.tasks, task)
        
        # Registrar para estatísticas
        if model_id:
            if model_id not in self.model_stats:
                self.model_stats[model_id] = {
                    "enqueued": 0,
                    "completed": 0,
                    "errors": 0,
                    "timeouts": 0,
                    "avg_latency": 0
                }
            self.model_stats[model_id]["enqueued"] += 1
        
        logger.debug(f"Tarefa {task_id} adicionada à fila (prioridade: {priority})")
        
        return task_id
    
    async def _worker_loop(self):
        """Loop principal de processamento da fila."""
        while self.running:
            if not self.tasks:
                # Fila vazia, aguardar
                await asyncio.sleep(0.1)
                continue
            
            # Obter próxima tarefa com maior prioridade
            task = heapq.heappop(self.tasks)
            
            # Verificar se já expirou
            elapsed = time.time() - task.timestamp
            if elapsed > task.timeout:
                logger.warning(f"Tarefa {task.task_id} expirou na fila após {elapsed:.2f}s")
                continue
            
            # Executar tarefa com o semáforo (limitando concorrência)
            async with self.semaphore:
                try:
                    # Configurar timeout
                    remaining_timeout = max(0.1, task.timeout - elapsed)
                    start_time = time.time()
                    
                    await asyncio.wait_for(task.coro, timeout=remaining_timeout)
                    
                    # Registrar estatísticas
                    latency = time.time() - start_time
                    logger.debug(f"Tarefa {task.task_id} completada em {latency:.2f}s")
                    
                except asyncio.TimeoutError:
                    logger.error(f"Tarefa {task.task_id} excedeu o timeout de {task.timeout}s")
                    
                except Exception as e:
                    logger.error(f"Erro ao processar tarefa {task.task_id}: {str(e)}")

# Singleton para acesso global
_queue_manager = None

def get_llm_queue_manager() -> LLMQueueManager:
    """Obtém a instância do gerenciador de fila LLM."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = LLMQueueManager()
    return _queue_manager