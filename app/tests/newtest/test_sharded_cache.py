# app/tests/newtest/test_sharded_cache.py - Versão corrigida
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import hashlib
import pickle
import asyncio
import time

from app.core.sharded_cache import ShardedCache

class TestShardedCache:
    @pytest.fixture
    def redis_nodes(self):
        """Fixture para nós Redis mockados."""
        return [MagicMock(), MagicMock(), MagicMock()]
    
    @pytest.fixture
    def sharded_cache(self, redis_nodes):
        """Fixture para cache shardado com nós mockados."""
        with patch('redis.asyncio.from_url', side_effect=redis_nodes):
            cache = ShardedCache(["redis://localhost:6379"] * 3)
            # Substituir os nós pelas nossas instâncias mockadas
            cache.nodes = redis_nodes
            return cache
    
    def test_get_shard_by_tenant(self, sharded_cache, redis_nodes):
        """Testa o sharding baseado em tenant."""
        # Cada tenant deve ir para um shard consistente
        tenant1 = "tenant-123"
        tenant2 = "tenant-456"
        
        # Mesmo tenant deve ir sempre para o mesmo shard
        shard1a = sharded_cache.get_shard("key1", tenant1)
        shard1b = sharded_cache.get_shard("key2", tenant1)
        assert shard1a == shard1b
        
        # Tenant diferente pode ir para shard diferente
        shard2 = sharded_cache.get_shard("key1", tenant2)
        # Não podemos garantir que será diferente do primeiro, mas é uma possibilidade
    
    def test_get_shard_by_key(self, sharded_cache, redis_nodes):
        """Testa o sharding baseado em chave."""
        # Configurar estratégia de sharding para "key"
        sharded_cache.strategy = "key"
        
        # Mesma chave deve ir sempre para o mesmo shard
        shard1a = sharded_cache.get_shard("specific-key")
        shard1b = sharded_cache.get_shard("specific-key")
        assert shard1a == shard1b
        
        # Chaves diferentes podem ir para shards diferentes
        shard2 = sharded_cache.get_shard("another-key")
        # Não podemos garantir que será diferente do primeiro, mas é uma possibilidade
    
    @pytest.mark.asyncio
    async def test_set_get(self, sharded_cache, redis_nodes):
        """Testa operações básicas de set e get."""
        # Mock para shard com funções async
        shard = MagicMock()
        
        # Criar funções assíncronas corretamente
        shard.set = AsyncMock(return_value=True)
        shard.get = AsyncMock(return_value=pickle.dumps({"test": "data"}))
        
        sharded_cache.get_shard = MagicMock(return_value=shard)
        
        # Testar set
        value = {"test": "data"}
        result = await sharded_cache.set("test-key", value, ttl=300, tenant_id="tenant-1")
        assert result == True
        
        # Testar get
        result = await sharded_cache.get("test-key", tenant_id="tenant-1")
        assert result == value

    @pytest.mark.asyncio
    async def test_flush_tenant(self, sharded_cache, redis_nodes):
        """Testa limpeza de dados por tenant."""
        # Configurar mocks com funções async
        keys = ["tenant:tenant-1:key1", "tenant:tenant-1:key2"]
        
        for node in redis_nodes:
            node.keys = AsyncMock(return_value=keys)
            node.delete = AsyncMock(return_value=len(keys))
        
        # Chamar o método
        result = await sharded_cache.flush_tenant("tenant-1")
        
        # Verificar resultado
        assert result == True

# tests/test_background_jobs.py
from app.core.background_jobs import BackgroundJobQueue, Job, JobStatus

class TestBackgroundJobs:
    @pytest.fixture
    def job_queue(self):
        """Fixture para a fila de jobs."""
        queue = BackgroundJobQueue(max_workers=2)
        # Importante: não iniciar automaticamente para evitar problemas nos testes
        queue.running = False
        return queue
    
    @pytest.mark.asyncio
    async def test_job_run_success(self):
        """Testa execução bem-sucedida de um job."""
        # Função assíncrona simulada
        async def success_func(a, b, c=3):
            await asyncio.sleep(0.01)  # Reduzir tempo para teste
            return a + b + c
        
        # Criar job
        job = Job(
            func=success_func,
            args=[1, 2],
            kwargs={"c": 4},
            timeout=1.0
        )
        
        # Executar
        await job.run()
        
        # Verificar resultado
        assert job.status == JobStatus.COMPLETED
        assert job.result == 7  # 1 + 2 + 4
        assert job.error is None
        assert job.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_job_run_failure(self):
        """Testa falha na execução de um job."""
        # Função que lança exceção
        async def error_func():
            await asyncio.sleep(0.01)  # Reduzir tempo para teste
            raise ValueError("Test error")
        
        # Criar job
        job = Job(
            func=error_func,
            args=[],
            kwargs={},
            timeout=1.0
        )
        
        # Executar
        await job.run()
        
        # Verificar resultado
        assert job.status == JobStatus.FAILED
        assert job.result is None
        assert "Test error" in job.error
        assert job.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_job_timeout(self):
        """Testa timeout de um job."""
        # Função que demora mais que o timeout
        async def slow_func():
            await asyncio.sleep(0.2)
            return "Done"
        
        # Criar job com timeout curto
        job = Job(
            func=slow_func,
            args=[],
            kwargs={},
            timeout=0.05  # Timeout menor que o tempo da função
        )
        
        # Executar
        await job.run()
        
        # Verificar resultado
        assert job.status == JobStatus.FAILED
        assert job.result is None
        assert "Timeout" in job.error
        assert job.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_queue_enqueue(self, job_queue):
        """Testa adição de job à fila."""
        # Função mock
        async def test_func():
            return "OK"
        
        # Patch o método start para evitar iniciar o worker loop
        with patch.object(job_queue, 'start', new_callable=AsyncMock) as mock_start:
            # Adicionar à fila
            job_id = await job_queue.enqueue(
                test_func,
                timeout=1.0,
                tenant_id="tenant-123"
            )
        
        # Verificar
        assert job_id is not None
        assert job_id in job_queue.jobs
        assert job_queue.jobs[job_id].tenant_id == "tenant-123"
        
        # Verificar que start foi chamado porque queue não estava rodando
        mock_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_queue_get_job(self, job_queue):
        """Testa obtenção de informações de um job."""
        # Função mock
        async def test_func():
            return "OK"
        
        # Patch o método start para evitar iniciar o worker loop
        with patch.object(job_queue, 'start', new_callable=AsyncMock):
            # Adicionar à fila
            job_id = await job_queue.enqueue(test_func)
        
        # Obter informações
        job_info = job_queue.get_job(job_id)
        
        # Verificar
        assert job_info is not None
        assert job_info["id"] == job_id
        assert job_info["status"] == JobStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_queue_cancel_job(self, job_queue):
        """Testa cancelamento de um job."""
        # Função mock
        async def test_func():
            await asyncio.sleep(1.0)
            return "OK"
        
        # Patch o método start para evitar iniciar o worker loop
        with patch.object(job_queue, 'start', new_callable=AsyncMock):
            # Adicionar à fila
            job_id = await job_queue.enqueue(test_func)
        
        # Cancelar
        result = job_queue.cancel_job(job_id)
        
        # Verificar
        assert result is True
        assert job_queue.jobs[job_id].status == JobStatus.CANCELLED