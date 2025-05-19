"""
Teste simplificado para a infraestrutura LLM
"""
import os
import sys
import logging
import asyncio

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Configurar variável de ambiente para SECRET_KEY
os.environ["SECRET_KEY"] = "test_secret_key"

# Definição da classe de teste
class SimpleLLMTest:
    async def run(self):
        print("="*80)
        print("TESTE SIMPLIFICADO DE INFRAESTRUTURA LLM")
        print("="*80)
        
        print("\nVerificando importações básicas...")
        try:
            from app.core.rate_limiter import get_rate_limiter
            print("✅ Rate Limiter importado com sucesso")
            
            from app.core.monitoring import get_llm_metrics
            print("✅ Monitoring importado com sucesso")
            
            from app.core.cache import get_cache
            print("✅ Cache importado com sucesso")
            
            from app.llm.router import llm_router
            print("✅ LLM Router importado com sucesso")
            
            # Tenta acessar os modelos registrados
            models = llm_router.list_models()
            print(f"✅ Modelos registrados: {len(models)}")
            for i, model in enumerate(models):
                print(f"  {i+1}. {model.get('model_id', 'desconhecido')}")
            
            print("\nTeste básico concluído com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro durante o teste: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    test = SimpleLLMTest()
    result = loop.run_until_complete(test.run())
    if not result:
        sys.exit(1)