# tests/test_llm_queue.py
import pytest
import asyncio
from unittest.mock import MagicMock, patch
import time

from app.llm.queue_manager import LLMQueueManager, PriorityTask

class TestLLMQueueManager:
    @pytest.fixture
    def queue_manager(self):
        """Fixture para o gerenciador de fila."""
        manager = LLMQueueManager(max_concurrent=3)
        return manager
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue_manager):
        """Testa se as tarefas são ordenadas corretamente por prioridade."""
        # Criar tarefas com diferentes prioridades
        task1 = PriorityTask(priority=5, task_id="task1", coro=MagicMock())
        task2 = PriorityTask(priority=2, task_id="task2", coro=MagicMock())  # Maior prioridade
        task3 = PriorityTask(priority=7, task_id="task3", coro=MagicMock())
        
        # Verificar ordenação (menor número = maior prioridade)
        assert task2 < task1 < task3
    
    @pytest.mark.asyncio
    async def test_enqueue(self, queue_manager):
        """Testa a adição de tarefas à fila."""
        # Criar coroutine mock
        async def mock_coro():
            return "result"
        
        # Adicionar à fila
        task_id = await queue_manager.enqueue(
            coro=mock_coro(),
            priority=3,
            model_id="test-model"
        )
        
        # Verificar resultado
        assert task_id is not None
        assert len(queue_manager.tasks) == 1
        assert queue_manager.tasks[0].priority == 3
        
        # Verificar estatísticas
        assert "test-model" in queue_manager.model_stats
        assert queue_manager.model_stats["test-model"]["enqueued"] == 1
    
    @pytest.mark.asyncio
    async def test_worker_loop(self, queue_manager):
        """Testa o loop de processamento da fila."""
        # Criar coroutine que retorna sucesso após delay
        async def success_coro():
            await asyncio.sleep(0.1)
            return "success"
        
        # Criar coroutine que falha
        async def error_coro():
            await asyncio.sleep(0.1)
            raise ValueError("Test error")
        
        # Configurar para iniciar e parar após um tempo
        queue_manager.running = True
        
        # Adicionar tarefas
        await queue_manager.enqueue(success_coro(), priority=1)
        await queue_manager.enqueue(error_coro(), priority=2)
        
        # Iniciar worker por um curto período
        worker_task = asyncio.create_task(queue_manager._worker_loop())
        await asyncio.sleep(0.5)  # Dar tempo para processar
        
        # Parar o worker
        queue_manager.running = False
        await worker_task
        
        # A fila deve estar vazia após processamento
        assert len(queue_manager.tasks) == 0
    
    
    @pytest.mark.asyncio
    async def test_start_stop(self, queue_manager):
        """Testa inicialização e parada da fila."""
        # Substituir _worker_loop por um coroutine mock em vez de MagicMock
        async def mock_worker():
            return None
            
        queue_manager._worker_loop = mock_worker
        
        # Iniciar
        await queue_manager.start()
        
        # Parar
        await queue_manager.stop()