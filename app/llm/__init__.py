# app/llm/__init__.py
from app.llm.base import LLMBase
from app.llm.llama import LlamaLLM
from app.llm.mistral import MistralLLM
from app.llm.deepseek import DeepSeekLLM
from app.llm.router import llm_router, initialize_models_from_config

# Inicializa os modelos a partir da configuração quando o módulo for importado
initialize_models_from_config()

__all__ = [
    "LLMBase", 
    "LlamaLLM", 
    "MistralLLM", 
    "DeepSeekLLM", 
    "llm_router",
    "initialize_models_from_config"
]