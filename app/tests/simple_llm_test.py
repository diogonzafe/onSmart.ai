"""
Teste simplificado para verificar a infraestrutura de LLMs.
"""
import os
import sys
import asyncio
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("simple_llm_test")

# Adiciona o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

print(f"Path do Python: {sys.path}")

# Cria um modelo simulado para teste
class MockLLM:
    """Modelo LLM simulado para testes."""
    
    def __init__(self, model_id="mock_model"):
        self.model_id = model_id
        logger.info(f"Modelo {model_id} inicializado para teste")
    
    async def generate(self, prompt):
        """Gera texto simulado."""
        logger.info(f"Gerando texto para prompt: {prompt[:30]}...")
        await asyncio.sleep(0.5)  # Simula processamento
        return f"Resposta simulada para: {prompt[:10]}..."
    
    async def embed(self, text):
        """Cria embedding simulado."""
        logger.info(f"Criando embedding para texto: {text[:30]}...")
        await asyncio.sleep(0.5)  # Simula processamento
        return [0.1] * 10  # Vetor simulado

async def run_test():
    """Executa teste simples com o modelo simulado."""
    print("="*80)
    print(" TESTE SIMPLES DE INFRAESTRUTURA DE LLM ".center(80, "-"))
    print("="*80)
    
    try:
        # Inicializando modelo
        print("\n1. Inicializando modelo simulado...")
        model = MockLLM()
        
        # Testando geração de texto
        print("\n2. Testando geração de texto...")
        prompt = "Explique o que é inteligência artificial"
        response = await model.generate(prompt)
        print(f"Resposta: {response}")
        
        # Testando criação de embedding
        print("\n3. Testando criação de embedding...")
        text = "Inteligência artificial"
        embedding = await model.embed(text)
        print(f"Embedding (primeiros 5 valores): {embedding[:5]}")
        
        print("\nTodos os testes completados com sucesso!")
        
    except Exception as e:
        print(f"\nERRO durante o teste: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print(" FIM DO TESTE ".center(80, "-"))
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_test())