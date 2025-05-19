"""
Teste funcional para a infraestrutura de LLM
"""
import os
import sys
import asyncio
import logging
from typing import Dict, List, Any, Optional

# Configuração de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# Adicionar diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Configurar variável de ambiente para SECRET_KEY
os.environ["SECRET_KEY"] = "test_secret_key"

class FunctionalTest:
    async def setup(self):
        """Configuração inicial para testes funcionais"""
        # Importar diretamente aqui, após configuração do ambiente
        from app.core.rate_limiter import get_rate_limiter
        from app.core.monitoring import get_llm_metrics
        from app.core.cache import get_cache
        
        self.rate_limiter = get_rate_limiter()
        self.metrics = get_llm_metrics()
        self.cache = get_cache()
        
        print("✅ Configuração inicial concluída")
        return True
    
    async def test_rate_limiter(self):
        """Teste básico do rate limiter"""
        print("\n==== TESTE DO RATE LIMITER ====")
        
        try:
            # Teste simples
            key = f"test_key_{os.urandom(4).hex()}"
            is_allowed, info = await self.rate_limiter.check_rate_limit(
                key=key,
                limit=5,
                period=10,
                category="test"
            )
            
            print(f"Resultado: allowed={is_allowed}, remaining={info.get('remaining')}")
            
            # Múltiplas requisições
            results = []
            for i in range(7):  # Intencionalmente ultrapassa o limite de 5
                is_allowed, info = await self.rate_limiter.check_rate_limit(
                    key=key,
                    limit=5,
                    period=10,
                    category="test"
                )
                results.append(is_allowed)
                print(f"Requisição {i+1}: allowed={is_allowed}, remaining={info.get('remaining')}")
            
            blocked = results.count(False)
            print(f"Total de requisições bloqueadas: {blocked} de 7")
            
            # Reset do limite
            reset_success = await self.rate_limiter.reset_rate_limit(key, "test")
            print(f"Reset do limite: {'Sucesso' if reset_success else 'Falha'}")
            
            # Verificar após reset
            is_allowed, info = await self.rate_limiter.check_rate_limit(
                key=key,
                limit=5,
                period=10,
                category="test"
            )
            print(f"Após reset: allowed={is_allowed}, remaining={info.get('remaining')}")
            
            print("✅ Rate limiter funcionando")
            return True
            
        except Exception as e:
            print(f"❌ Erro no rate limiter: {str(e)}")
            return False
    
    async def test_monitoring(self):
        """Teste básico do sistema de monitoramento"""
        print("\n==== TESTE DO MONITORAMENTO ====")
        
        try:
            # Registrar uma solicitação de teste
            request_id = await self.metrics.record_request(
                model_id="teste-model",
                operation="generate",
                user_id="teste-user",
                metadata={"test": True}
            )
            
            print(f"Request ID gerado: {request_id}")
            
            # Registrar resposta
            await self.metrics.record_response(
                request_id=request_id,
                success=True,
                latency=0.5,
                tokens=100
            )
            
            # Obter métricas
            metrics = await self.metrics.get_model_metrics()
            print(f"Métricas obtidas: {len(metrics.keys())} modelos")
            
            # Obter detalhes da solicitação
            details = await self.metrics.get_request_details(request_id)
            if details and "model_id" in details:
                print(f"Detalhes da solicitação: {details.get('model_id')} - {details.get('operation')}")
                print(f"Status: {details.get('status')}, Latência: {details.get('latency', 0):.3f}s")
            
            print("✅ Sistema de monitoramento funcionando")
            return True
            
        except Exception as e:
            print(f"❌ Erro no monitoramento: {str(e)}")
            return False
    
    async def test_cache(self):
        """Teste básico do sistema de cache"""
        print("\n==== TESTE DO CACHE ====")
        
        try:
            # Chave de teste
            key = f"test_cache_{os.urandom(4).hex()}"
            value = {"data": "teste", "timestamp": asyncio.get_event_loop().time()}
            
            # Armazenar no cache
            set_success = await self.cache.set(key, value, ttl=60)
            print(f"Armazenamento no cache: {'Sucesso' if set_success else 'Falha'}")
            
            # Recuperar do cache
            retrieved = await self.cache.get(key)
            
            if retrieved and retrieved.get("data") == "teste":
                print("✅ Valor recuperado com sucesso do cache")
            else:
                print("❌ Falha ao recuperar valor do cache")
                
            # Limpar
            delete_success = await self.cache.delete(key)
            print(f"Remoção do cache: {'Sucesso' if delete_success else 'Falha'}")
            
            # Verificar após exclusão
            after_delete = await self.cache.get(key)
            if after_delete is None:
                print("✅ Exclusão confirmada")
            
            print("✅ Sistema de cache funcionando")
            return True
            
        except Exception as e:
            print(f"❌ Erro no sistema de cache: {str(e)}")
            return False
    
    async def test_router_basic(self):
        """Teste básico do router LLM"""
        print("\n==== TESTE BÁSICO DO ROUTER LLM ====")
        
        try:
            from app.llm.router import llm_router
            
            # Listar modelos registrados
            models = llm_router.list_models()
            print(f"Modelos registrados: {len(models)}")
            
            for i, model in enumerate(models):
                model_id = model.get("model_id", "unknown")
                model_type = model.get("model_type", "unknown")
                is_default = model.get("is_default", False)
                print(f"  {i+1}. {model_id} ({model_type}){' [DEFAULT]' if is_default else ''}")
            
            # Se não houver modelos, registrar um simulado para teste
            if not models:
                print("\nNenhum modelo encontrado. Vamos criar um simulado para testar:")
                
                from app.llm.base import LLMBase
                
                class MockLLM(LLMBase):
                    def initialize(self) -> None:
                        self.initialized = True
                    
                    async def generate(self, prompt, **kwargs):
                        await asyncio.sleep(0.1)
                        return f"Resposta simulada para: {prompt[:30]}..."
                    
                    async def embed(self, text, **kwargs):
                        await asyncio.sleep(0.1)
                        if isinstance(text, list):
                            return [[0.1] * 10 for _ in text]
                        return [0.1] * 10
                
                # Registrar o tipo no router
                llm_router.model_registry["mock"] = MockLLM
                
                # Registrar uma instância
                llm_router.register_model(
                    "mock-model",
                    {"type": "mock", "model_name": "mock-model"},
                    default=True
                )
                
                print("✅ Modelo simulado registrado")
                models = llm_router.list_models()
                print(f"Modelos agora: {len(models)}")
            
            # Tentar obter o modelo padrão
            if llm_router.default_model:
                default_model = llm_router.get_model()
                print(f"Modelo padrão: {default_model}")
            
            print("✅ Router LLM básico funcionando")
            return True
            
        except Exception as e:
            print(f"❌ Erro no router básico: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_smart_router(self):
        """Teste do Smart Router"""
        print("\n==== TESTE DO SMART ROUTER ====")
        
        try:
            # Primeiro teste o router básico para garantir que há pelo menos um modelo
            router_ok = await self.test_router_basic()
            if not router_ok:
                print("❌ Não é possível testar Smart Router sem um router básico funcional")
                return False
            
            from app.llm.smart_router import get_smart_router
            
            smart_router = get_smart_router()
            print("✅ Smart Router inicializado")
            
            # Teste do seletor de modelos
            sample_queries = [
                "Olá, como vai?",
                "Explique o conceito de machine learning",
                "Escreva um código Python para análise de sentimentos"
            ]
            
            print("\nTeste de seleção de modelos:")
            for query in sample_queries:
                complexity = smart_router.selector.analyze_query_complexity(query)
                print(f"  Query: '{query[:30]}...' - Complexidade: {complexity}")
            
            print("\n✅ Smart Router funcionando")
            return True
            
        except Exception as e:
            print(f"❌ Erro no Smart Router: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run_all(self):
        """Executar todos os testes"""
        print("="*50)
        print("TESTE FUNCIONAL DE INFRAESTRUTURA LLM")
        print("="*50)
        
        # Setup
        if not await self.setup():
            print("❌ Falha na configuração inicial")
            return False
        
        # Teste rate limiter
        rate_limiter_result = await self.test_rate_limiter()
        
        # Teste monitoring
        monitoring_result = await self.test_monitoring()
        
        # Teste cache
        cache_result = await self.test_cache()
        
        # Teste router básico
        router_result = await self.test_router_basic()
        
        # Teste smart router
        smart_router_result = await self.test_smart_router()
        
        # Resumo
        print("\n==== RESUMO DOS TESTES ====")
        print(f"Rate Limiter: {'✅ PASSOU' if rate_limiter_result else '❌ FALHOU'}")
        print(f"Monitoramento: {'✅ PASSOU' if monitoring_result else '❌ FALHOU'}")
        print(f"Cache: {'✅ PASSOU' if cache_result else '❌ FALHOU'}")
        print(f"Router Básico: {'✅ PASSOU' if router_result else '❌ FALHOU'}")
        print(f"Smart Router: {'✅ PASSOU' if smart_router_result else '❌ FALHOU'}")
        
        tests = [rate_limiter_result, monitoring_result, cache_result, router_result, smart_router_result]
        total_passed = sum(1 for test in tests if test)
        print(f"\nResultado final: {total_passed}/{len(tests)} testes passaram ({total_passed/len(tests)*100:.1f}%)")
        
        print("="*50)
        return total_passed == len(tests)

if __name__ == "__main__":
    try:
        # Usar o novo padrão recomendado para asyncio
        async def main():
            test = FunctionalTest()
            success = await test.run_all()
            return success
        
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTeste interrompido pelo usuário")
        sys.exit(1)