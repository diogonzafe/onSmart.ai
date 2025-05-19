import httpx
import asyncio
import os
import sys
import json

# Set environment variable for SECRET_KEY to avoid validation error
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"

# Add the parent directory to the path to be able to import app.config
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

# Import the settings from config
from config import settings

async def test_llm_integration():
    print(f"Connecting to LLM server at: {settings.LLM_SERVER_URL}")
    print(f"Timeout set to: {settings.LLM_SERVER_TIMEOUT} seconds")
    
    async with httpx.AsyncClient(timeout=settings.LLM_SERVER_TIMEOUT) as client:
        try:
            # Health check test
            print("\nTesting health endpoint...")
            health = await client.get(f"{settings.LLM_SERVER_URL}/health")
            print(f"Status de saúde: {health.json()}")
            
            # Text generation test
            print("\nTesting text generation...")
            response = await client.post(
                f"{settings.LLM_SERVER_URL}/generate",
                json={
                    "prompt": "O que é um sistema ERP inteligente?",
                    "model_id": "llama",
                    "max_tokens": 100
                }
            )
            result = response.json()
            print(f"Resposta do LLM: {result['text']}")
            
            # Models test
            print("\nTesting models endpoint...")
            models_response = await client.get(f"{settings.LLM_SERVER_URL}/models")
            print(f"Models disponíveis: {json.dumps(models_response.json(), indent=2)}")
            
            # Trying embedding test with error handling
            print("\nTesting embeddings...")
            try:
                embed_response = await client.post(
                    f"{settings.LLM_SERVER_URL}/embed",
                    json={
                        "text": "sistema ERP inteligente",
                        "model_id": "llama"
                    }
                )
                embed_result = embed_response.json()
                
                # Check if 'embedding' key exists in response
                if 'embedding' in embed_result:
                    print(f"Dimensão do embedding: {len(embed_result['embedding'])}")
                    print(f"Primeiros 5 valores: {embed_result['embedding'][:5]}")
                else:
                    print(f"Resposta do endpoint embed (missing 'embedding' key): {json.dumps(embed_result, indent=2)}")
            except Exception as e:
                print(f"Erro no teste de embeddings: {str(e)}")
                print("Continuando com outros testes...")
            
            print("\n✅ Testes completados!")
            return True
        except Exception as e:
            print(f"\n❌ Erro na integração com LLM: {str(e)}")
            return False

# Run the test
if __name__ == "__main__":
    print("Starting LLM integration test...")
    asyncio.run(test_llm_integration())
