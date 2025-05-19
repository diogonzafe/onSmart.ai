import httpx
import asyncio
import os
import sys

# Add the parent directory to the path to be able to import app.config
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

# Try to import from config, but provide fallback if it doesn't exist
try:
    from config import LLM_SERVER_URL, LLM_SERVER_TIMEOUT
except ImportError:
    print("Config file not found, using default values")
    LLM_SERVER_URL = "http://192.168.15.35:8000"  # Using your local IP
    LLM_SERVER_TIMEOUT = 120

async def test_llm_integration():
    print(f"Connecting to LLM server at: {LLM_SERVER_URL}")
    print(f"Timeout set to: {LLM_SERVER_TIMEOUT} seconds")
    
    async with httpx.AsyncClient(timeout=LLM_SERVER_TIMEOUT) as client:
        try:
            # Health check test
            print("\nTesting health endpoint...")
            health = await client.get(f"{LLM_SERVER_URL}/health")
            print(f"Status de saúde: {health.json()}")
            
            # Text generation test
            print("\nTesting text generation...")
            response = await client.post(
                f"{LLM_SERVER_URL}/generate",
                json={
                    "prompt": "O que é um sistema ERP inteligente?",
                    "model_id": "llama",
                    "max_tokens": 100
                }
            )
            result = response.json()
            print(f"Resposta do LLM: {result['text']}")
            
            # Embedding test
            print("\nTesting embeddings...")
            embed_response = await client.post(
                f"{LLM_SERVER_URL}/embed",
                json={
                    "text": "sistema ERP inteligente",
                    "model_id": "llama"
                }
            )
            embed_result = embed_response.json()
            print(f"Dimensão do embedding: {len(embed_result['embedding'])}")
            print(f"Primeiros 5 valores: {embed_result['embedding'][:5]}")
            
            print("\n✅ Todos os testes completados com sucesso!")
            return True
        except Exception as e:
            print(f"\n❌ Erro na integração com LLM: {str(e)}")
            return False

# Run the test
if __name__ == "__main__":
    print("Starting LLM integration test...")
    asyncio.run(test_llm_integration())
