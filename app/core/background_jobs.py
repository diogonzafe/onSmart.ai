# app/core/background_jobs.py
import logging
import asyncio
import uuid
import time
import json
from typing import Dict, List, Any, Optional, Callable, Awaitable
from enum import Enum
import traceback

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job:
    """Representação de um job assíncrono."""
    
    def __init__(self, 
                func: Callable[..., Awaitable[Any]], 
                args: List[Any], 
                kwargs: Dict[str, Any], 
                timeout: Optional[float] = None,
                tenant_id: Optional[str] = None):
        self.id = str(uuid.uuid4())
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.status = JobStatus.PENDING
        self.result = None
        self.error = None
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.timeout = timeout
        self.tenant_id = tenant_id
        self.task = None
    
    async def run(self):
        """Executa o job."""
        self.status = JobStatus.RUNNING
        self.started_at = time.time()
        
        try:
            if self.timeout:
                # Executar com timeout
                self.result = await asyncio.wait_for(
                    self.func(*self.args, **self.kwargs),
                    timeout=self.timeout
                )
            else:
                # Executar sem timeout
                self.result = await self.func(*self.args, **self.kwargs)
            
            self.status = JobStatus.COMPLETED
        except asyncio.TimeoutError:
            self.status = JobStatus.FAILED
            self.error = "Timeout exceeded"
        except Exception as e:
            self.status = JobStatus.FAILED
            self.error = str(e)
            logger.error(f"Job {self.id} failed: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            self.completed_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte o job para dicionário."""
        return {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed": self.completed_at - self.started_at if self.completed_at and self.started_at else None,
            "result": self.result if not isinstance(self.result, (bytes, bytearray)) else "<binary>",
            "error": self.error,
            "tenant_id": self.tenant_id
        }
    
    def cancel(self):
        """Cancela o job."""
        if self.status == JobStatus.PENDING or self.status == JobStatus.RUNNING:
            self.status = JobStatus.CANCELLED
            if self.task and not self.task.done():
                self.task.cancel()

class BackgroundJobQueue:
    """
    Fila de jobs em background.
    Processa tarefas assíncronas em segundo plano.
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Inicializa a fila de jobs.
        
        Args:
            max_workers: Número máximo de workers
        """
        self.jobs: Dict[str, Job] = {}
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        self.running = False
        self.worker_task = None
    
    async def start(self):
        """Inicia o processamento da fila."""
        if self.running:
            return
        
        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"Background job queue iniciada com {self.max_workers} workers")
    
    async def stop(self):
        """Para o processamento da fila."""
        if not self.running:
            return
        
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            self.worker_task = None
        
        logger.info("Background job queue parada")
    
    async def enqueue(self, 
               func: Callable[..., Awaitable[Any]], 
               *args, 
               timeout: Optional[float] = None,
               tenant_id: Optional[str] = None,
               auto_start: bool = True,  # Novo parâmetro
               **kwargs) -> str:
        """
        Adiciona um job à fila.
        
        Args:
            func: Função a ser executada
            *args: Argumentos posicionais
            timeout: Timeout em segundos
            tenant_id: ID do tenant (para isolamento)
            auto_start: Se deve iniciar automaticamente a fila (padrão: True)
            **kwargs: Argumentos nomeados
            
        Returns:
            ID do job
        """
        job = Job(func, args, kwargs, timeout, tenant_id)
        self.jobs[job.id] = job
        
        # Se a fila não estiver rodando e auto_start for True, iniciar
        if not self.running and auto_start:
            await self.start()
        
        logger.info(f"Job {job.id} adicionado à fila")
        return job.id
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações sobre um job.
        
        Args:
            job_id: ID do job
            
        Returns:
            Informações do job ou None se não encontrado
        """
        job = self.jobs.get(job_id)
        if job:
            return job.to_dict()
        return None
    
    def get_tenant_jobs(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Obtém todos os jobs de um tenant.
        
        Args:
            tenant_id: ID do tenant
            
        Returns:
            Lista de informações de jobs
        """
        return [job.to_dict() for job in self.jobs.values() 
                if job.tenant_id == tenant_id]
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancela um job.
        
        Args:
            job_id: ID do job
            
        Returns:
            True se o job foi cancelado, False caso contrário
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        job.cancel()
        return True
    
    async def _worker_loop(self):
        """Loop principal de processamento da fila."""
        while self.running:
            # Encontrar jobs pendentes
            pending_jobs = [job for job in self.jobs.values() 
                          if job.status == JobStatus.PENDING]
            
            if not pending_jobs:
                # Sem jobs pendentes, aguardar
                await asyncio.sleep(0.1)
                continue
            
            # Executar jobs pendentes (até o limite de workers)
            for job in pending_jobs:
                # Usar semáforo para limitar número de jobs simultâneos
                if await self._try_acquire_semaphore():
                    # Iniciar job em task separada
                    job.task = asyncio.create_task(self._run_job(job))
    
    async def _try_acquire_semaphore(self) -> bool:
        """Tenta adquirir o semáforo sem bloquear."""
        if self.semaphore.locked():
            return False
        
        await self.semaphore.acquire()
        return True
    
    async def _run_job(self, job: Job):
        """
        Executa um job e libera o semáforo após concluir.
        
        Args:
            job: Job a ser executado
        """
        try:
            await job.run()
        finally:
            self.semaphore.release()

# Singleton para acesso global
_job_queue = None

def get_background_job_queue() -> BackgroundJobQueue:
    """Obtém a instância da fila de jobs."""
    global _job_queue
    if _job_queue is None:
        _job_queue = BackgroundJobQueue()
    return _job_queue