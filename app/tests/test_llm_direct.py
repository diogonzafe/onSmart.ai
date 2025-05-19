import httpx
import asyncio
import json

# Direct configuration without importing from config
LLM_SERVER_URL = "http://192.168.15.35:8000"
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
            
            # Models test
            print("\nTesting models endpoint...")
            models_response = await client.get(f"{LLM_SERVER_URL}/models")
            print(f"Models disponíveis: {json.dumps(models_response.json(), indent=2)}")
            
            print("\n✅ Testes básicos completados com sucesso!")
            return True
        except Exception as e:
            print(f"\n❌ Erro na integração com LLM: {str(e)}")
            return False

# Run the test
if __name__ == "__main__":
    print("Starting LLM integration test...")
    asyncio.run(test_llm_integration())
