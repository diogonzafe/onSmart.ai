"""
Teste específico para o LLMRouter.
"""
import os
import sys
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, AsyncGenerator

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("router_test")

# Adiciona o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

print(f"Path do Python: {sys.path}")

# Importar o router e a classe base
from app.llm.base import LLMBase
from app.llm.router import LLMRouter

# Criar uma implementação simulada de LLM para testes
class MockLLM(LLMBase):
    """Implementação simulada para testes."""
    
    def initialize(self) -> None:
        """Inicializa o modelo."""
        self.initialized = True
        logger.info(f"Mock LLM inicializado: {self.model_name}")
    
    async def generate(self, 
                  prompt: str, 
                  max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None,
                  stream: bool = False,
                  **kwargs) -> Union[str, AsyncGenerator[str, None]]:
        """Gera texto simulado."""
        logger.info(f"Gerando texto com modelo {self.model_name} para prompt: {prompt[:30]}...")
        await asyncio.sleep(0.5)  # Simula processamento
        
        if stream:
            async def fake_stream():
                tokens = ["Este", "é", "um", "texto", "simulado", "do", "modelo", self.model_name]
                for token in tokens:
                    await asyncio.sleep(0.1)
                    yield token
            return fake_stream()
        else:
            return f"Este é um texto simulado do modelo {self.model_name} para: {prompt[:20]}..."
    
    async def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Cria embedding simulado."""
        logger.info(f"Criando embedding com modelo {self.model_name}")
        await asyncio.sleep(0.5)  # Simula processamento
        
        # Cria um vetor simulado de 10 dimensões
        if isinstance(text, str):
            return [0.1] * 10
        else:
            return [[0.1] * 10 for _ in text]

async def test_router():
    """Testa o LLMRouter com modelos simulados."""
    print("="*80)
    print(" TESTE DO LLM ROUTER ".center(80, "-"))
    print("="*80)
    
    try:
        # Criando o router
        print("\n1. Criando LLMRouter...")
        router = LLMRouter()
        
        # Registrando modelos simulados
        print("\n2. Registrando modelos simulados...")
        router.model_registry["mock"] = MockLLM
        
        router.register_model(
            "modelo1",
            {"type": "mock", "model_name": "modelo1"},
            default=True
        )
        
        router.register_model(
            "modelo2",
            {"type": "mock", "model_name": "modelo2"},
            default=False
        )
        
        # Listando modelos
        print("\n3. Listando modelos disponíveis...")
        models = router.list_models()
        print(f"Total de modelos: {len(models)}")
        for model_info in models:
            is_default = "(padrão)" if model_info["is_default"] else ""
            print(f"  - {model_info['model_id']} {is_default}")
        
        # Testando geração via modelo específico
        print("\n4. Testando geração com modelo específico...")
        prompt = "Explique o que é inteligência artificial"
        
        model = router.get_model("modelo1")
        response = await model.generate(prompt)
        print(f"Resposta do modelo1: {response}")
        
        # Testando geração via router
        print("\n5. Testando geração via router...")
        response = await router.route_generate(prompt)
        print(f"Resposta via router: {response}")
        
        # Testando fallback
        print("\n6. Testando mecanismo de fallback...")
        
        # Substituindo temporariamente o modelo1 por uma versão que falha
        original_model = router.models["modelo1"]
        
        class FailingLLM(MockLLM):
            async def generate(self, *args, **kwargs):
                raise Exception("Erro simulado para testar fallback")
        
        # Substituir com o modelo que falha
        router.models["modelo1"] = FailingLLM({"model_name": "failing_model"})
        
        # Tentar gerar com fallback
        response = await router.route_generate(
            prompt=prompt,
            model_id="modelo1",
            fallback=True
        )
        print(f"Resposta após fallback: {response}")
        
        # Restaurar o modelo original
        router.models["modelo1"] = original_model
        
        print("\nTodos os testes do router completados com sucesso!")
        
    except Exception as e:
        print(f"\nERRO durante o teste: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print(" FIM DO TESTE ".center(80, "-"))
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_router())