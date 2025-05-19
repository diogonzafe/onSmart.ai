# app/llm/router.py
import asyncio
import time
import random
from typing import Dict, Any, List, Optional, Union, Type, AsyncGenerator
import logging

from app.llm.base import LLMBase
from app.llm.llama import LlamaLLM
from app.llm.mistral import MistralLLM
from app.llm.deepseek import DeepSeekLLM
from app.llm.http_client import HttpLLM  # Nova importação
from app.config import settings

logger = logging.getLogger(__name__)

class LLMRouter:
    """
    Sistema de roteamento para selecionar e gerenciar diferentes implementações de LLM.
    """
    
    def __init__(self):
        self.models: Dict[str, LLMBase] = {}
        self.default_model: Optional[str] = None
        self.model_registry: Dict[str, Type[LLMBase]] = {
            "llama": LlamaLLM,
            "mistral": MistralLLM,
            "deepseek": DeepSeekLLM,
            "http": HttpLLM  # Novo tipo adicionado
        }
    
    def register_model(self, model_id: str, model_config: Dict[str, Any], default: bool = False) -> None:
        """
        Registra um novo modelo no router.
        
        Args:
            model_id: Identificador único para o modelo
            model_config: Configuração do modelo
            default: Se True, define este modelo como o padrão
        """
        model_type = model_config.get("type", "").lower()
        
        if model_type not in self.model_registry:
            raise ValueError(f"Tipo de modelo não suportado: {model_type}")
        
        # Cria a instância do modelo
        model_class = self.model_registry[model_type]
        try:
            model_instance = model_class(model_config)
            self.models[model_id] = model_instance
            logger.info(f"Modelo {model_id} ({model_type}) registrado com sucesso")
            
            # Se for o padrão ou não houver modelo padrão ainda
            if default or self.default_model is None:
                self.default_model = model_id
                logger.info(f"Modelo {model_id} definido como padrão")
                
        except Exception as e:
            logger.error(f"Erro ao registrar modelo {model_id}: {str(e)}")
            raise
    
    def get_model(self, model_id: Optional[str] = None) -> LLMBase:
        """
        Obtém um modelo pelo ID ou o modelo padrão.
        
        Args:
            model_id: ID do modelo a ser obtido (opcional)
            
        Returns:
            Instância do modelo solicitado
        """
        model_id = model_id or self.default_model
        
        if not model_id:
            raise ValueError("Nenhum modelo registrado ou modelo padrão definido")
        
        if model_id not in self.models:
            raise ValueError(f"Modelo não encontrado: {model_id}")
        
        return self.models[model_id]
    
    async def route_generate(self, 
                      prompt: str,
                      model_id: Optional[str] = None,
                      fallback: bool = True,
                      **kwargs) -> Union[str, AsyncGenerator[str, None]]:
        """
        Roteia a solicitação de geração para o modelo apropriado com fallback.
        
        Args:
            prompt: Texto de entrada
            model_id: ID do modelo a ser usado (opcional)
            fallback: Se True, tenta outros modelos em caso de falha
            **kwargs: Parâmetros adicionais para geração
            
        Returns:
            Texto gerado ou gerador de streaming
        """
        # Se nenhum modelo for especificado, use o padrão
        target_id = model_id or self.default_model
        
        if not target_id:
            raise ValueError("Nenhum modelo disponível para geração")
        
        # Lista de modelos a tentar (começa com o solicitado)
        models_to_try = [target_id]
        
        # Se fallback estiver habilitado, adiciona outros modelos à lista
        if fallback and len(self.models) > 1:
            # Adiciona todos os outros modelos em ordem aleatória
            remaining_models = [m for m in self.models if m != target_id]
            random.shuffle(remaining_models)
            models_to_try.extend(remaining_models)
        
        # Tenta cada modelo na lista
        last_error = None
        for current_id in models_to_try:
            try:
                model = self.get_model(current_id)
                start_time = time.time()
                
                # Tenta gerar texto com o modelo atual
                result = await model.generate(prompt, **kwargs)
                
                # Se não for o modelo original solicitado, registra que usou fallback
                if current_id != target_id:
                    logger.info(f"Fallback para modelo {current_id} bem-sucedido")
                
                # Registra métricas de tempo
                generation_time = time.time() - start_time
                logger.debug(f"Modelo {current_id} gerou resposta em {generation_time:.2f}s")
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Erro com modelo {current_id}: {str(e)}")
                
                # Se for streaming, não podemos prosseguir para outros modelos
                if kwargs.get("stream", False):
                    logger.error("Não é possível fazer fallback para streaming")
                    raise e
                
                # Continua para o próximo modelo se houver fallback
                continue
        
        # Se chegou aqui, todos os modelos falharam
        error_msg = f"Todos os modelos falharam. Último erro: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    async def route_embed(self, 
                    text: Union[str, List[str]],
                    model_id: Optional[str] = None,
                    fallback: bool = True) -> Union[List[float], List[List[float]]]:
        """
        Roteia a solicitação de embeddings para o modelo apropriado com fallback.
        
        Args:
            text: Texto ou lista de textos
            model_id: ID do modelo a ser usado (opcional)
            fallback: Se True, tenta outros modelos em caso de falha
            
        Returns:
            Vetor de embedding ou lista de vetores
        """
        # Se nenhum modelo for especificado, use o padrão
        target_id = model_id or self.default_model
        
        if not target_id:
            raise ValueError("Nenhum modelo disponível para embeddings")
        
        # Lista de modelos a tentar (começa com o solicitado)
        models_to_try = [target_id]
        
        # Se fallback estiver habilitado, adiciona outros modelos à lista
        if fallback and len(self.models) > 1:
            # Adiciona todos os outros modelos em ordem aleatória
            remaining_models = [m for m in self.models if m != target_id]
            random.shuffle(remaining_models)
            models_to_try.extend(remaining_models)
        
        # Tenta cada modelo na lista
        last_error = None
        for current_id in models_to_try:
            try:
                model = self.get_model(current_id)
                start_time = time.time()
                
                # Tenta criar embeddings com o modelo atual
                result = await model.embed(text)
                
                # Se não for o modelo original solicitado, registra que usou fallback
                if current_id != target_id:
                    logger.info(f"Fallback para modelo {current_id} para embeddings bem-sucedido")
                
                # Registra métricas de tempo
                embedding_time = time.time() - start_time
                logger.debug(f"Modelo {current_id} gerou embeddings em {embedding_time:.2f}s")
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Erro com modelo {current_id} para embeddings: {str(e)}")
                
                # Continua para o próximo modelo se houver fallback
                continue
        
        # Se chegou aqui, todos os modelos falharam
        error_msg = f"Todos os modelos falharam para embeddings. Último erro: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Lista todos os modelos registrados e suas informações.
        
        Returns:
            Lista de informações dos modelos
        """
        models_info = []
        for model_id, model in self.models.items():
            info = model.get_model_info()
            info["model_id"] = model_id
            info["is_default"] = (model_id == self.default_model)
            models_info.append(info)
        
        return models_info

# Cria uma instância global do router
llm_router = LLMRouter()

# Inicializa os modelos a partir das configurações
def initialize_models_from_config():
    """Inicializa modelos com base nas configurações."""
    try:
        # Configurações para Llama (local)
        if hasattr(settings, "LLAMA_MODEL_PATH") and settings.LLAMA_MODEL_PATH:
            llm_router.register_model(
                "llama",
                {
                    "type": "llama",
                    "model_name": "llama",
                    "model_path": settings.LLAMA_MODEL_PATH,
                    "n_ctx": getattr(settings, "LLAMA_N_CTX", 4096),
                    "n_gpu_layers": getattr(settings, "LLAMA_N_GPU_LAYERS", -1),
                    "verbose": getattr(settings, "LLAMA_VERBOSE", False)
                },
                default=True
            )
        
        # Configurações para Mistral
        if hasattr(settings, "MISTRAL_API_KEY") and settings.MISTRAL_API_KEY:
            llm_router.register_model(
                "mistral",
                {
                    "type": "mistral",
                    "model_name": getattr(settings, "MISTRAL_MODEL", "mistral-medium"),
                    "api_key": settings.MISTRAL_API_KEY,
                    "api_url": getattr(settings, "MISTRAL_API_URL", "https://api.mistral.ai/v1"),
                    "embedding_model": getattr(settings, "MISTRAL_EMBEDDING_MODEL", "mistral-embed")
                },
                default=not llm_router.default_model  # Define como padrão se não houver outro
            )
        
        # Configurações para DeepSeek
        if hasattr(settings, "DEEPSEEK_API_KEY") and settings.DEEPSEEK_API_KEY:
            llm_router.register_model(
                "deepseek",
                {
                    "type": "deepseek",
                    "model_name": getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
                    "api_key": settings.DEEPSEEK_API_KEY,
                    "api_url": getattr(settings, "DEEPSEEK_API_URL", "https://api.deepseek.com/v1"),
                    "embedding_model": getattr(settings, "DEEPSEEK_EMBEDDING_MODEL", "deepseek-embed")
                },
                default=not llm_router.default_model  # Define como padrão se não houver outro
            )
        
        # Configurações para servidor LLM HTTP
        if hasattr(settings, "LLM_SERVER_URL") and settings.LLM_SERVER_URL:
            # Registrar modelos HTTP
            llm_router.register_model(
                "llama-http",
                {
                    "type": "http",
                    "model_name": "llama-http",
                    "target_model": "llama",
                    "server_url": settings.LLM_SERVER_URL,
                    "timeout": settings.LLM_SERVER_TIMEOUT
                },
                default=not llm_router.default_model  # Define como padrão se não houver outro
            )
            
            # Registrar modelo mistral via HTTP
            llm_router.register_model(
                "mistral-http",
                {
                    "type": "http",
                    "model_name": "mistral-http",
                    "target_model": "mistral",
                    "server_url": settings.LLM_SERVER_URL,
                    "timeout": settings.LLM_SERVER_TIMEOUT
                },
                default=False
            )
            
            logger.info(f"Modelos HTTP registrados apontando para {settings.LLM_SERVER_URL}")
        
        if not llm_router.models:
            logger.warning("Nenhum modelo LLM foi configurado. Os serviços de LLM não estarão disponíveis.")
        else:
            logger.info(f"Inicializados {len(llm_router.models)} modelos LLM. Modelo padrão: {llm_router.default_model}")
            
    except Exception as e:
        logger.error(f"Erro ao inicializar modelos LLM: {str(e)}")