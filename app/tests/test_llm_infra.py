"""
Script para testar a infraestrutura de LLMs.
Testa a interface base, as implementações específicas e o sistema de roteamento.
"""
import os
import sys
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
import random

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("llm_test")

# Adiciona o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Importa os módulos necessários
from app.llm.base import LLMBase
from app.llm.llama import LlamaLLM
from app.llm.mistral import MistralLLM
from app.llm.deepseek import DeepSeekLLM
from app.llm.router import LLMRouter, llm_router, initialize_models_from_config
from app.core.cache import Cache, get_cache
from app.config import settings

class LLMInfrastructureTester:
    """
    Classe para testar a infraestrutura de LLMs.
    """
    
    def __init__(self):
        self.router = llm_router
        self.cache = get_cache()
        
        # Prompts de teste
        self.test_prompts = [
            "Explique o conceito de aprendizado de máquina em poucas palavras.",
            "O que é um modelo de linguagem?",
            "Liste 3 vantagens de usar Python para desenvolvimento.",
            "Escreva um parágrafo curto sobre inteligência artificial.",
            "Qual é a diferença entre IA generativa e IA discriminativa?"
        ]
        
        # Textos para teste de embeddings
        self.test_texts = [
            "Inteligência artificial", 
            "Aprendizado de máquina", 
            "Processamento de linguagem natural",
            "Redes neurais",
            "Transformers e atenção"
        ]
    
    def print_separator(self, title=None):
        """Imprime um separador com título opcional para melhor legibilidade."""
        print("\n" + "="*80)
        if title:
            print(f" {title} ".center(80, "-"))
        print("="*80 + "\n")
    
   # Modifique o método test_llm_initialization em app/tests/test_llm_infra.py

async def test_llm_initialization(self):
    """Testa a inicialização dos modelos LLM."""
    self.print_separator("TESTE DE INICIALIZAÇÃO DE MODELOS")
    
    # Lista os modelos disponíveis
    models = self.router.list_models()
    
    if not models:
        logger.warning("Nenhum modelo LLM foi inicializado.")
        # Vamos criar um modelo simulado para testes
        self.router.register_model(
            "mock_model",
            {
                "type": "mistral",  # Use qualquer tipo que exista na registry
                "model_name": "mock_model",
                "api_key": "dummy_key",
                "api_url": "https://example.com",
                "embedding_model": "mock_embed"
            },
            default=True
        )
        logger.info("Modelo simulado registrado para testes.")
        models = self.router.list_models()
    
    # Mostra informações sobre os modelos
    logger.info(f"Total de modelos registrados: {len(models)}")
    
    for model_info in models:
        model_id = model_info["model_id"]
        model_type = model_info["model_type"]
        is_default = model_info["is_default"]
        
        status = "✅ (Padrão)" if is_default else "✅"
        logger.info(f"{status} Modelo {model_id} ({model_type}) inicializado.")
        
        # Mostra configurações do modelo (sem chaves de API)
        safe_config = {k: v for k, v in model_info["config"].items() if "key" not in k.lower()}
        logger.info(f"    Configuração: {safe_config}")
    
    logger.info(f"Modelo padrão: {self.router.default_model}")
    
    return len(models) > 0
    
    async def test_text_generation(self, model_id=None):
        """
        Testa a geração de texto com um modelo específico ou o padrão.
        
        Args:
            model_id: ID do modelo a ser testado (opcional)
        """
        if model_id:
            model_name = model_id
            title = f"TESTE DE GERAÇÃO DE TEXTO - MODELO {model_id}"
        else:
            model_name = "padrão"
            title = "TESTE DE GERAÇÃO DE TEXTO - MODELO PADRÃO"
            
        self.print_separator(title)
        
        # Seleciona um prompt aleatório
        prompt = random.choice(self.test_prompts)
        logger.info(f"Prompt de teste: '{prompt}'")
        
        try:
            # Obtém o modelo
            model = self.router.get_model(model_id)
            logger.info(f"Usando modelo: {model}")
            
            # Mede o tempo de geração
            start_time = time.time()
            
            # Gera o texto
            generated_text = await model.generate(
                prompt=prompt,
                max_tokens=200,
                temperature=0.7
            )
            
            # Calcula o tempo decorrido
            elapsed_time = time.time() - start_time
            
            logger.info(f"Texto gerado em {elapsed_time:.2f} segundos pelo modelo {model_name}:")
            print("-"*40)
            print(generated_text)
            print("-"*40)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao gerar texto com o modelo {model_name}: {str(e)}")
            return False
    
    async def test_embedding_creation(self, model_id=None):
        """
        Testa a criação de embeddings com um modelo específico ou o padrão.
        
        Args:
            model_id: ID do modelo a ser testado (opcional)
        """
        if model_id:
            model_name = model_id
            title = f"TESTE DE CRIAÇÃO DE EMBEDDINGS - MODELO {model_id}"
        else:
            model_name = "padrão"
            title = "TESTE DE CRIAÇÃO DE EMBEDDINGS - MODELO PADRÃO"
            
        self.print_separator(title)
        
        # Seleciona um texto aleatório
        text = random.choice(self.test_texts)
        logger.info(f"Texto de teste: '{text}'")
        
        try:
            # Obtém o modelo
            model = self.router.get_model(model_id)
            
            # Mede o tempo de geração do embedding
            start_time = time.time()
            
            # Cria o embedding
            embedding = await model.embed(text=text)
            
            # Calcula o tempo decorrido
            elapsed_time = time.time() - start_time
            
            # Mostra informações sobre o embedding
            embedding_type = type(embedding).__name__
            embedding_length = len(embedding)
            
            logger.info(f"Embedding criado em {elapsed_time:.2f} segundos pelo modelo {model_name}:")
            logger.info(f"Tipo: {embedding_type}, Dimensão: {embedding_length}")
            
            # Mostra os primeiros valores do embedding
            preview = embedding[:5]
            logger.info(f"Primeiros 5 valores: {preview}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar embedding com o modelo {model_name}: {str(e)}")
            return False
    
    async def test_router_generate(self):
        """Testa a geração de texto através do router."""
        self.print_separator("TESTE DE GERAÇÃO DE TEXTO VIA ROUTER")
        
        # Seleciona um prompt aleatório
        prompt = random.choice(self.test_prompts)
        logger.info(f"Prompt de teste: '{prompt}'")
        
        try:
            # Mede o tempo de geração
            start_time = time.time()
            
            # Gera o texto através do router
            generated_text = await self.router.route_generate(
                prompt=prompt,
                fallback=True,
                max_tokens=200,
                temperature=0.7
            )
            
            # Calcula o tempo decorrido
            elapsed_time = time.time() - start_time
            
            logger.info(f"Texto gerado em {elapsed_time:.2f} segundos via router:")
            print("-"*40)
            print(generated_text)
            print("-"*40)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao gerar texto via router: {str(e)}")
            return False
    
    async def test_router_embed(self):
        """Testa a criação de embeddings através do router."""
        self.print_separator("TESTE DE CRIAÇÃO DE EMBEDDINGS VIA ROUTER")
        
        # Seleciona um texto aleatório
        text = random.choice(self.test_texts)
        logger.info(f"Texto de teste: '{text}'")
        
        try:
            # Mede o tempo de geração
            start_time = time.time()
            
            # Cria o embedding através do router
            embedding = await self.router.route_embed(
                text=text,
                fallback=True
            )
            
            # Calcula o tempo decorrido
            elapsed_time = time.time() - start_time
            
            # Mostra informações sobre o embedding
            embedding_type = type(embedding).__name__
            embedding_length = len(embedding)
            
            logger.info(f"Embedding criado em {elapsed_time:.2f} segundos via router:")
            logger.info(f"Tipo: {embedding_type}, Dimensão: {embedding_length}")
            
            # Mostra os primeiros valores do embedding
            preview = embedding[:5]
            logger.info(f"Primeiros 5 valores: {preview}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar embedding via router: {str(e)}")
            return False
    
    async def test_model_fallback(self):
        """Testa o mecanismo de fallback entre modelos."""
        self.print_separator("TESTE DE FALLBACK ENTRE MODELOS")
        
        models = self.router.list_models()
        if len(models) < 2:
            logger.warning("Não é possível testar fallback: menos de 2 modelos disponíveis.")
            return False
        
        # Escolhe um modelo que não é o padrão para simular erro
        non_default_models = [m["model_id"] for m in models if not m["is_default"]]
        
        if not non_default_models:
            logger.warning("Não há modelos além do padrão para testar fallback.")
            return False
        
        test_model_id = non_default_models[0]
        logger.info(f"Testando fallback do modelo {test_model_id} para o modelo padrão.")
        
        # Cria uma classe personalizada de LLM que sempre falha
        class FailingLLM(LLMBase):
            def initialize(self) -> None:
                pass
                
            async def generate(self, *args, **kwargs):
                raise Exception("Erro simulado para testar fallback")
                
            async def embed(self, *args, **kwargs):
                raise Exception("Erro simulado para testar fallback")
        
        # Salva a instância original
        original_model = self.router.models[test_model_id]
        
        try:
            # Substitui com o modelo que falha
            self.router.models[test_model_id] = FailingLLM({"model_name": "failing_model"})
            
            # Tenta gerar texto com fallback
            prompt = random.choice(self.test_prompts)
            logger.info(f"Prompt de teste: '{prompt}'")
            
            start_time = time.time()
            
            # Deve falhar no primeiro modelo e usar fallback
            result = await self.router.route_generate(
                prompt=prompt,
                model_id=test_model_id,
                fallback=True
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info(f"Fallback bem-sucedido em {elapsed_time:.2f} segundos:")
            print("-"*40)
            print(result)
            print("-"*40)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no teste de fallback: {str(e)}")
            return False
        finally:
            # Restaura o modelo original
            self.router.models[test_model_id] = original_model
    
    async def test_cache(self):
        """Testa o sistema de cache para respostas."""
        self.print_separator("TESTE DE CACHE")
        
        if not hasattr(self.cache, "redis") or self.cache.redis is None:
            logger.warning("Não foi possível conectar ao Redis. Ignorando teste de cache.")
            return False
        
        # Criamos uma chave de teste única
        test_key = f"test:llm:{int(time.time())}"
        test_value = {"text": "Isto é um valor de teste", "timestamp": time.time()}
        
        try:
            # Testa armazenamento no cache
            logger.info(f"Armazenando valor no cache com chave: {test_key}")
            await self.cache.set(test_key, test_value, ttl=60)
            
            # Testa recuperação do cache
            logger.info("Recuperando valor do cache...")
            retrieved_value = await self.cache.get(test_key)
            
            if retrieved_value and retrieved_value["text"] == test_value["text"]:
                logger.info("✅ Valor recuperado do cache com sucesso.")
            else:
                logger.error("❌ Falha ao recuperar valor do cache.")
                return False
            
            # Testa exclusão do cache
            logger.info("Excluindo valor do cache...")
            await self.cache.delete(test_key)
            
            # Verifica se foi excluído
            deleted_check = await self.cache.get(test_key)
            
            if deleted_check is None:
                logger.info("✅ Valor excluído do cache com sucesso.")
            else:
                logger.error("❌ Falha ao excluir valor do cache.")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no teste de cache: {str(e)}")
            return False
        
    async def run_all_tests(self):
        """Executa todos os testes em sequência."""
        self.print_separator("INICIANDO TESTES DE INFRAESTRUTURA DE LLMs")
        
        # Resultados dos testes
        results = {}
        
        # Etapa 1: Teste de inicialização dos modelos
        results["initialization"] = await self.test_llm_initialization()
        
        # Verifica se temos modelos para continuar
        if not results["initialization"]:
            logger.error("Não há modelos inicializados. Abortando testes.")