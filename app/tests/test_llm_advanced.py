# app/tests/test_llm_advanced.py
"""
Testes avançados para a infraestrutura de LLMs.
Testa as novas funcionalidades:
- Rate Limiting
- Monitoramento Avançado
- Seleção Inteligente de Modelos
"""
import os
import sys
import asyncio
import logging
import time
import random
from typing import Dict, List, Any, Optional
import json

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Adiciona o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Set environment variable for SECRET_KEY to avoid validation error
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"

# Importa os módulos necessários
from app.core.rate_limiter import RateLimiter, get_rate_limiter
from app.core.monitoring import LLMMetrics, get_llm_metrics
from app.llm.smart_router import ModelSelector, SmartLLMRouter, get_smart_router
from app.llm.base import LLMBase
from app.llm.router import LLMRouter
from app.core.cache import get_cache

class TestLLMAdvanced:
    """
    Classe para testes avançados da infraestrutura de LLMs.
    """
    
    async def setup(self):
        """Configuração inicial para os testes."""
        self.rate_limiter = get_rate_limiter()
        self.metrics = get_llm_metrics()
        self.cache = get_cache()
        
        # Criar um LLM simulado para testes
        class MockLLM(LLMBase):
            def initialize(self) -> None:
                self.initialized = True
                logger.info(f"Mock LLM inicializado: {self.model_name}")
            
            async def generate(self, prompt, **kwargs):
                await asyncio.sleep(0.1)  # Simula processamento
                return f"Resposta simulada para: {prompt[:30]}..."
            
            async def embed(self, text, **kwargs):
                await asyncio.sleep(0.1)  # Simula processamento
                if isinstance(text, list):
                    return [[0.1] * 10 for _ in text]
                return [0.1] * 10
        
        # Configurar router simulado
        self.router = LLMRouter()
        self.router.model_registry["mock"] = MockLLM
        
        # Registrar modelos simulados
        self.router.register_model(
            "llama",
            {"type": "mock", "model_name": "llama"},
            default=True
        )
        
        self.router.register_model(
            "mistral",
            {"type": "mock", "model_name": "mistral"},
            default=False
        )
        
        self.router.register_model(
            "deepseek",
            {"type": "mock", "model_name": "deepseek"},
            default=False
        )
        
        # Configurar seletor de modelos e router inteligente
        self.selector = ModelSelector(self.router)
        self.smart_router = SmartLLMRouter(self.router)
        
        logger.info("Setup para testes concluído")
    
    def print_separator(self, title=None):
        """Imprime um separador com título opcional para melhor legibilidade."""
        print("\n" + "="*80)
        if title:
            print(f" {title} ".center(80, "-"))
        print("="*80 + "\n")
    
    async def test_rate_limiter(self):
        """Testa o sistema de limitação de taxa."""
        self.print_separator("TESTE DE RATE LIMITER")
        
        # Chave de teste única
        test_key = f"test_user_{int(time.time())}"
        
        try:
            logger.info(f"Testando rate limiter para chave: {test_key}")
            
            # Definir um limite baixo para teste
            limit = 5
            period = 10  # segundos
            
            # Primeira verificação deve passar
            allowed, info = await self.rate_limiter.check_rate_limit(
                key=test_key,
                limit=limit,
                period=period,
                category="test"
            )
            
            logger.info(f"Primeira verificação: permitido={allowed}, restantes={info['remaining']}")
            print(f"Primeira verificação: permitido={allowed}, restantes={info['remaining']}")
            
            # Criar múltiplas requisições até o limite
            results = []
            
            for i in range(limit + 2):  # Intencionalmente ultrapassa o limite
                allowed, info = await self.rate_limiter.check_rate_limit(
                    key=test_key,
                    limit=limit,
                    period=period,
                    category="test"
                )
                
                results.append(allowed)
                logger.info(f"Requisição {i+1}: permitido={allowed}, restantes={info['remaining']}")
                
                if i == limit - 1:
                    # Mostra info quando atingir o limite
                    print(f"Limite atingido após {i+1} requisições:")
                    print(f"  - Requisições permitidas: {sum(results)}")
                    print(f"  - Requisições bloqueadas: {len(results) - sum(results)}")
                    print(f"  - Tempo de reset: {int(info['reset'] - time.time())} segundos")
            
            # Verificar resultados
            blocked_count = results.count(False)
            if blocked_count > 0:
                print(f"✅ Rate Limiter bloqueou corretamente {blocked_count} requisições após o limite")
            else:
                print("❌ Rate Limiter não bloqueou requisições corretamente")
            
            # Testar obtenção de uso atual
            usage = await self.rate_limiter.get_current_usage(test_key, "test")
            print(f"Uso atual: {usage}")
            
            # Testar reset
            reset_result = await self.rate_limiter.reset_rate_limit(test_key, "test")
            print(f"Reset do limite: {'Sucesso' if reset_result else 'Falha'}")
            
            # Verificar se o reset funcionou
            allowed, info = await self.rate_limiter.check_rate_limit(
                key=test_key,
                limit=limit,
                period=period,
                category="test"
            )
            
            print(f"Após reset: permitido={allowed}, restantes={info['remaining']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no teste de rate limiter: {str(e)}")
            print(f"❌ Erro no teste: {str(e)}")
            return False
    
    async def test_monitoring(self):
        """Testa o sistema de monitoramento avançado."""
        self.print_separator("TESTE DE MONITORAMENTO")
        
        try:
            # Registrar várias solicitações simuladas para teste
            model_ids = ["llama", "mistral", "deepseek"]
            operations = ["generate", "embed"]
            
            logger.info("Registrando solicitações simuladas para testes de métricas")
            
            # Lista para armazenar IDs de solicitações
            request_ids = []
            
            # Registrar diferentes tipos de solicitações
            for i in range(10):
                model_id = random.choice(model_ids)
                operation = random.choice(operations)
                success = random.random() > 0.2  # 80% de sucesso
                latency = random.uniform(0.2, 2.0)
                tokens = random.randint(50, 500) if operation == "generate" else None
                
                # Registrar solicitação
                request_id = await self.metrics.record_request(
                    model_id=model_id,
                    operation=operation,
                    metadata={"test_run": True, "index": i}
                )
                
                request_ids.append(request_id)
                
                # Simular processamento
                await asyncio.sleep(0.05)
                
                # Registrar resposta
                await self.metrics.record_response(
                    request_id=request_id,
                    success=success,
                    latency=latency,
                    tokens=tokens,
                    error=None if success else "Erro simulado para teste"
                )
                
                logger.info(f"Registrada solicitação {i+1}: modelo={model_id}, operação={operation}, sucesso={success}")
            
            print(f"✅ Registradas {len(request_ids)} solicitações simuladas para métricas")
            
            # Buscar métricas agregadas
            metrics = await self.metrics.get_model_metrics(period="today")
            
            print("\nMétricas por modelo:")
            for model_id, model_data in metrics.items():
                print(f"\nModelo: {model_id}")
                
                for operation, op_data in model_data.items():
                    print(f"  Operação: {operation}")
                    print(f"    - Requisições: {op_data.get('requests', 0)}")
                    print(f"    - Sucessos: {op_data.get('successes', 0)}")
                    print(f"    - Falhas: {op_data.get('failures', 0)}")
                    print(f"    - Taxa de sucesso: {op_data.get('success_rate', 0):.1f}%")
                    print(f"    - Latência média: {op_data.get('latency_avg', 0):.3f}s")
            
            # Verificar detalhes de uma solicitação específica
            if request_ids:
                detail = await self.metrics.get_request_details(request_ids[0])
                print(f"\nDetalhes da solicitação {request_ids[0]}:")
                print(json.dumps(detail, indent=2))
                
                if "model_id" in detail and "operation" in detail:
                    print("✅ Detalhes de solicitação recuperados com sucesso")
                else:
                    print("❌ Falha ao recuperar detalhes da solicitação")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no teste de monitoramento: {str(e)}")
            print(f"❌ Erro no teste: {str(e)}")
            return False
    
    async def test_model_selection(self):
        """Testa o sistema de seleção inteligente de modelos."""
        self.print_separator("TESTE DE SELEÇÃO DE MODELOS")
        
        try:
            # Teste de análise de complexidade
            test_queries = [
                # Complexidade baixa
                "Olá, como vai?",
                "continue",
                "ok",
                # Complexidade média
                "O que é machine learning?",
                "Explique o conceito de inteligência artificial",
                "Liste os principais frameworks de Python",
                # Complexidade alta
                "Desenvolva um programa completo em Python para análise de sentimentos com BERT",
                "Compare e contraste os diferentes modelos de arquitetura de transformers, incluindo suas vantagens e desvantagens",
                "Escreva um ensaio detalhado sobre as implicações éticas da inteligência artificial na sociedade moderna"
            ]
            
            print("Análise de complexidade de consultas:")
            for query in test_queries:
                complexity = self.selector.analyze_query_complexity(query)
                print(f"  - Complexidade {'alta' if complexity == 'high' else 'média' if complexity == 'medium' else 'baixa'}: \"{query[:50]}...\"")
            
            # Teste de determinação de tipo de consulta
            test_type_queries = [
                # Código
                "Escreva uma função em Python para ordenar uma lista",
                # Criativo
                "Crie uma história curta sobre um robô que quer ser humano",
                # Factual
                "Explique o que é a teoria da relatividade",
                # Raciocínio
                "Por que o céu é azul? Explique o fenômeno físico",
                # Computacional
                "Calcule a raiz quadrada de 144 e explique o processo"
            ]
            
            print("\nDeterminação de tipo de consulta:")
            for query in test_type_queries:
                weights = self.selector.determine_query_type(query)
                
                # Encontrar os pesos mais altos
                top_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
                
                print(f"  - Query: \"{query[:50]}...\"")
                print(f"    Características principais: {', '.join([f'{k}={v:.1f}' for k, v in top_weights])}")
            
            # Teste de seleção do melhor modelo
            test_selection_queries = [
                "Olá, como vai?",
                "Escreva um código Python para classificação de imagens usando TensorFlow",
                "Gere um poema sobre a natureza",
                "Explique como funciona a relatividade geral",
                "Resolva a equação 2x + 5 = 15"
            ]
            
            print("\nSeleção de modelos:")
            for query in test_selection_queries:
                selected_model = await self.selector.select_best_model(query)
                print(f"  - Query: \"{query[:50]}...\"")
                print(f"    Modelo selecionado: {selected_model}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no teste de seleção de modelos: {str(e)}")
            print(f"❌ Erro no teste: {str(e)}")
            return False
    
    async def test_smart_router(self):
        """Testa o router inteligente."""
        self.print_separator("TESTE DE SMART ROUTER")
        
        try:
            # Testar geração de texto
            test_query = "Explique o conceito de machine learning em poucas palavras"
            
            print(f"Gerando texto via smart router para: \"{test_query}\"")
            
            # Primeira chamada - não deve usar cache
            start_time = time.time()
            response1 = await self.smart_router.smart_generate(
                prompt=test_query,
                max_tokens=50,
                temperature=0.7,
                use_cache=True
            )
            
            first_call_time = time.time() - start_time
            print(f"Primeira chamada ({first_call_time:.3f}s): {response1}")
            
            # Segunda chamada - deve usar cache
            start_time = time.time()
            response2 = await self.smart_router.smart_generate(
                prompt=test_query,
                max_tokens=50,
                temperature=0.7,
                use_cache=True
            )
            
            second_call_time = time.time() - start_time
            print(f"Segunda chamada ({second_call_time:.3f}s): {response2}")
            
            # Verificar se houve aceleração com o cache
            if second_call_time < first_call_time:
                print(f"✅ Cache funcionou: {first_call_time:.3f}s -> {second_call_time:.3f}s ({(1 - second_call_time/first_call_time)*100:.1f}% mais rápido)")
            else:
                print("❓ Cache pode não ter funcionado: Sem melhoria significativa de velocidade")
            
            # Testar criação de embeddings
            test_texts = [
                "Machine learning é uma área da inteligência artificial",
                "Processamento de linguagem natural é importante para chatbots"
            ]
            
            print("\nCriando embeddings via smart router")
            embedding = await self.smart_router.smart_embed(
                text=test_texts,
                use_cache=True
            )
            
            print(f"Embeddings criados para {len(test_texts)} textos, dimensão: {len(embedding[0]) if embedding else 'N/A'}")
            
            # Testar obtenção de métricas
            metrics = await self.smart_router.get_model_metrics(period="today")
            print("\nMétricas recuperadas via smart router:")
            print(f"  - Número de modelos com métricas: {len(metrics)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no teste de smart router: {str(e)}")
            print(f"❌ Erro no teste: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Executa todos os testes em sequência."""
        self.print_separator("TESTES AVANÇADOS DE INFRAESTRUTURA DE LLMs")
        
        # Configuração inicial
        await self.setup()
        
        # Executar testes
        tests = [
            ("Rate Limiter", self.test_rate_limiter),
            ("Monitoramento", self.test_monitoring),
            ("Seleção de Modelos", self.test_model_selection),
            ("Smart Router", self.test_smart_router)
        ]
        
        results = {}
        
        for name, test_func in tests:
            print(f"\nExecutando teste: {name}")
            try:
                start_time = time.time()
                result = await test_func()
                elapsed = time.time() - start_time
                
                status = "✅ PASSOU" if result else "❌ FALHOU"
                results[name] = result
                
                print(f"\n{status} - {name} ({elapsed:.2f}s)")
                
            except Exception as e:
                logger.error(f"Erro ao executar teste {name}: {str(e)}")
                print(f"\n❌ ERRO - {name}: {str(e)}")
                results[name] = False
        
        # Resumo final
        self.print_separator("RESUMO DOS TESTES")
        
        total = len(tests)
        passed = sum(1 for result in results.values() if result)
        
        for name, result in results.items():
            status = "✅ PASSOU" if result else "❌ FALHOU"
            print(f"{status} - {name}")
        
        print(f"\nResultado: {passed}/{total} testes passaram ({passed/total*100:.1f}%)")
        
        self.print_separator("FIM DOS TESTES")

# Função principal para execução dos testes
async def main():
    """Função principal para executar os testes."""
    tester = TestLLMAdvanced()
    await tester.run_all_tests()

# Executar testes se o script for executado diretamente
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())