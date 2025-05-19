# app/llm/smart_router.py
import time
import logging
import random
import re
from typing import Dict, List, Any, Optional, Union, Tuple, AsyncGenerator
import asyncio
from collections import defaultdict

from app.llm.base import LLMBase
from app.llm.router import LLMRouter, llm_router
from app.core.rate_limiter import get_rate_limiter
from app.core.monitoring import get_llm_metrics, monitor_llm
from app.core.cache import get_cache

# Removida a importação circular:
# from app.api import auth, users, llm_api

logger = logging.getLogger(__name__)

class ModelSelector:
    """
    Seletor inteligente de modelos LLM com base em características da consulta.
    """
    
    def __init__(self, router: LLMRouter):
        """
        Inicializa o seletor de modelos.
        
        Args:
            router: Instância do LLMRouter para acessar os modelos
        """
        self.router = router
        self.metrics = get_llm_metrics()
        self.cache = get_cache()
        self.rate_limiter = get_rate_limiter()
        
        # Padrões para análise de complexidade de consultas
        self.complexity_patterns = {
            "high": [
                r"(GPT-4|Claude|Gemini|Llama|análise|crítica|aprofundada|detalhada)",
                r"(compare|diferença|similaridade).{0,30}(entre|dos|nos)",
                r"(Por que|qual motivo|explique).{0,50}(fenômeno|conceito|técnica)",
                r"(escreva|criar|elabore|desenvolva|planeje).{0,20}(artigo|código|ensaio|análise)",
                r"(traduza|converta|transforme).{0,30}(para|em).{0,30}(formato|linguagem)",
                r"(resumir|sintetizar|condensar).{0,30}(livro|artigo|texto|pesquisa)",
                r"(passo\s+a\s+passo|metodologia|processo|como\s+fazer).{0,30}(complexo|completo)",
                r"(como|maneira|estratégia).{0,50}(resolver|implementar|desenvolver)",
                r"(forneça|liste|enumere).{0,20}(exemplos|casos|situações).{0,30}(múltiplos|diversos)",
                r"(discussão|debate|argumento).{0,30}(prós e contras|vantagens|desvantagens)"
            ],
            "medium": [
                r"(descreva|conte|explique|fale sobre).{0,30}(como|por que|quando)",
                r"(o que|qual|quais|quem|onde|quando).{0,40}(é|são|foi|foram|pode|podem)",
                r"(lista|exemplos|pontos).{0,20}(simples|básicos|principais)",
                r"(definir|significado|conceito).{0,20}(de|do|da|dos|das)",
                r"(resumo|síntese).{0,20}(breve|concisa|simples|curta)"
            ],
            "low": [
                r"(olá|oi|hey|e aí|sim|não|obrigado|legal|entendi)",
                r"(continue|prossiga|e depois|próximo)",
                r"^\s*\?+\s*$",  # Apenas pontos de interrogação
                r"^\s*[^.!?\s]{1,3}\s*$"  # Palavras muito curtas
            ]
        }
        
        # Características dos modelos para seleção inteligente
        self.model_characteristics = {
            # Valores padrão - serão atualizados à medida que o sistema analisa desempenho
            # higher is better, 1-10 scale
            "default": {
                "creativity": 5,
                "factual_accuracy": 5,
                "code_quality": 5,
                "reasoning": 5,
                "computation": 5,
                "conciseness": 5,
                "language_quality": 5,
                "cost_efficiency": 5,
                "speed": 5,
                "context_length": 5
            }
        }
        
        # Inicializar características específicas de modelos conhecidos
        self._initialize_model_characteristics()
    
    def _initialize_model_characteristics(self) -> None:
        """
        Inicializa características para modelos comuns.
        Estas são estimativas iniciais que serão refinadas com dados reais.
        """
        # LLaMA (local)
        llama_characteristics = {
            "creativity": 6,
            "factual_accuracy": 6,
            "code_quality": 7,
            "reasoning": 6,
            "computation": 5,
            "conciseness": 5,
            "language_quality": 6,
            "cost_efficiency": 10,  # Custo zero sendo local
            "speed": 4,  # Mais lento em hardware modesto
            "context_length": 7
        }
        
        # Mistral
        mistral_characteristics = {
            "creativity": 7,
            "factual_accuracy": 7,
            "code_quality": 8,
            "reasoning": 7,
            "computation": 6,
            "conciseness": 6,
            "language_quality": 7,
            "cost_efficiency": 5,
            "speed": 8,
            "context_length": 6
        }
        
        # DeepSeek
        deepseek_characteristics = {
            "creativity": 6,
            "factual_accuracy": 7,
            "code_quality": 9,  # Muito bom em código
            "reasoning": 7,
            "computation": 7,
            "conciseness": 7,
            "language_quality": 6,
            "cost_efficiency": 6,
            "speed": 7,
            "context_length": 6
        }
        
        # Atualizar dicionário de características
        for model_id in self.router.models:
            model = self.router.models[model_id]
            model_type = model.__class__.__name__.lower()
            
            if "llama" in model_type or "llama" in model_id.lower():
                self.model_characteristics[model_id] = llama_characteristics.copy()
            elif "mistral" in model_type or "mistral" in model_id.lower():
                self.model_characteristics[model_id] = mistral_characteristics.copy()
            elif "deepseek" in model_type or "deepseek" in model_id.lower():
                self.model_characteristics[model_id] = deepseek_characteristics.copy()
            else:
                # Modelo desconhecido - usar valores padrão
                self.model_characteristics[model_id] = self.model_characteristics["default"].copy()
                
            logger.info(f"Características inicializadas para modelo {model_id}")
    
    def analyze_query_complexity(self, query: str) -> str:
        """
        Analisa a complexidade de uma consulta.
        
        Args:
            query: Texto da consulta
            
        Returns:
            Nível de complexidade: 'high', 'medium' ou 'low'
        """
        # Verificar comprimento da consulta
        query_length = len(query.split())
        
        # Consultas muito longas são consideradas complexas
        if query_length > 100:
            return "high"
        elif query_length < 5:
            return "low"
        
        # Verificar padrões em ordem decrescente de complexidade
        for complexity, patterns in self.complexity_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return complexity
        
        # Se nenhum padrão corresponder, default para medium
        return "medium"
    
    def determine_query_type(self, query: str) -> Dict[str, float]:
        """
        Determina o tipo de consulta e os pesos de importância para diferentes características.
        
        Args:
            query: Texto da consulta
            
        Returns:
            Dicionário com pesos para diferentes características
        """
        # Padrões para tipos de consulta
        is_code_query = bool(re.search(r"(código|code|programa|function|def\s+|class\s+|```|import\s+)", query, re.IGNORECASE))
        is_creative_query = bool(re.search(r"(crie|imagine|invente|write\s+a|story|fiction|creative|poema|poem|história)", query, re.IGNORECASE))
        is_factual_query = bool(re.search(r"(explique|defina|o que é|what is|define|explain|quando|where|who|history|como|how to)", query, re.IGNORECASE))
        is_reasoning_query = bool(re.search(r"(por que|why|reason|explain|solve|resolver|provar|prove|logic|lógica|análise|analyze)", query, re.IGNORECASE))
        is_computation_query = bool(re.search(r"(calcule|compute|calculate|solve|math|equation|formula|número|número|estatística|statistics)", query, re.IGNORECASE))
        
        # Pesos padrão
        weights = {
            "creativity": 1.0,
            "factual_accuracy": 1.0,
            "code_quality": 1.0,
            "reasoning": 1.0,
            "computation": 1.0,
            "conciseness": 1.0,
            "language_quality": 1.0,
            "cost_efficiency": 1.0,
            "speed": 1.0,
            "context_length": 1.0
        }
        
        # Ajustar pesos com base no tipo de consulta
        if is_code_query:
            weights["code_quality"] = 2.5
            weights["reasoning"] = 1.5
            weights["factual_accuracy"] = 1.5
            weights["creativity"] = 0.5
        
        if is_creative_query:
            weights["creativity"] = 2.5
            weights["language_quality"] = 1.5
            weights["factual_accuracy"] = 0.5
        
        if is_factual_query:
            weights["factual_accuracy"] = 2.5
            weights["reasoning"] = 1.5
            weights["creativity"] = 0.5
        
        if is_reasoning_query:
            weights["reasoning"] = 2.5
            weights["factual_accuracy"] = 1.5
            weights["computation"] = 1.2
        
        if is_computation_query:
            weights["computation"] = 2.5
            weights["reasoning"] = 1.5
            weights["factual_accuracy"] = 1.2
        
        # Complexidade influencia o comprimento do contexto e eficiência
        complexity = self.analyze_query_complexity(query)
        if complexity == "high":
            weights["context_length"] = 2.0
            weights["reasoning"] = max(weights["reasoning"], 1.5)
        elif complexity == "low":
            weights["speed"] = 1.5
            weights["cost_efficiency"] = 1.5
        
        return weights
    
    async def get_operational_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtém métricas operacionais atuais para os modelos.
        
        Returns:
            Dicionário de métricas por modelo
        """
        model_metrics = {}
        
        # Verificar se o sistema de métricas está disponível
        try:
            metrics_data = await self.metrics.get_model_metrics(period="today")
            
            for model_id in self.router.models:
                if model_id in metrics_data:
                    model_data = metrics_data[model_id]
                    
                    # Calcular a taxa média de sucesso
                    if "generate" in model_data:
                        success_rate = model_data["generate"].get("success_rate", 100)
                        latency_avg = model_data["generate"].get("latency_avg", 1.0)
                    else:
                        success_rate = 100
                        latency_avg = 1.0
                    
                    model_metrics[model_id] = {
                        "success_rate": success_rate,
                        "latency": latency_avg,
                        "available": True
                    }
                else:
                    # Sem dados de métricas - assumir valores padrão
                    model_metrics[model_id] = {
                        "success_rate": 100,
                        "latency": 1.0,
                        "available": True
                    }
                
        except Exception as e:
            logger.error(f"Erro ao obter métricas operacionais: {str(e)}")
            
            # Valores padrão para todos os modelos
            for model_id in self.router.models:
                model_metrics[model_id] = {
                    "success_rate": 100,
                    "latency": 1.0,
                    "available": True
                }
        
        return model_metrics
    
    async def check_rate_limits(self) -> Dict[str, bool]:
        """
        Verifica os limites de taxa para os modelos.
        
        Returns:
            Dicionário indicando quais modelos estão disponíveis
        """
        availability = {}
        
        # Verificar cada modelo
        for model_id in self.router.models:
            try:
                # Verificação genérica para o modelo
                is_allowed, _ = await self.rate_limiter.check_rate_limit(
                    key=model_id,
                    limit=100,  # Limite padrão por modelo
                    period=60,
                    category="check"
                )
                
                availability[model_id] = is_allowed
                
            except Exception as e:
                logger.error(f"Erro ao verificar rate limit para {model_id}: {str(e)}")
                # Em caso de erro, assumir que o modelo está disponível
                availability[model_id] = True
        
        return availability
    
    async def select_best_model(
        self, 
        query: str,
        operation: str = "generate",
        preferred_model: Optional[str] = None
    ) -> str:
        """
        Seleciona o melhor modelo para uma consulta específica.
        
        Args:
            query: Texto da consulta
            operation: Tipo de operação ('generate' ou 'embed')
            preferred_model: ID do modelo preferido (opcional)
            
        Returns:
            ID do modelo selecionado
        """
        # Se um modelo específico for solicitado e disponível, usá-lo
        if preferred_model and preferred_model in self.router.models:
            logger.info(f"Usando modelo preferido: {preferred_model}")
            return preferred_model
        
        # Obter os modelos disponíveis
        rate_limits = await self.check_rate_limits()
        operational_metrics = await self.get_operational_metrics()
        
        available_models = []
        for model_id in self.router.models:
            if rate_limits.get(model_id, True) and operational_metrics.get(model_id, {}).get("available", True):
                available_models.append(model_id)
        
        if not available_models:
            # Se nenhum modelo estiver disponível, usar o padrão
            logger.warning("Nenhum modelo disponível, usando o padrão")
            return self.router.default_model
        
        # Para embeddings, usar o modelo padrão (mais simples)
        if operation == "embed":
            logger.info(f"Operação de embedding, usando modelo padrão: {available_models[0]}")
            return available_models[0]
        
        # Para geração de texto, selecionar com base nas características da consulta
        
        # 1. Analisar tipo e complexidade da consulta
        query_weights = self.determine_query_type(query)
        
        # 2. Calcular pontuação para cada modelo
        model_scores = {}
        
        for model_id in available_models:
            # Obter características do modelo
            characteristics = self.model_characteristics.get(model_id, self.model_characteristics["default"])
            
            # Cálculo de pontuação ponderada
            score = 0
            for characteristic, weight in query_weights.items():
                score += characteristics.get(characteristic, 5) * weight
            
            # Ajustar por métricas operacionais
            op_metrics = operational_metrics.get(model_id, {})
            success_rate = op_metrics.get("success_rate", 100)
            latency = op_metrics.get("latency", 1.0)
            
            # Ajustes de pontuação baseados em métricas operacionais
            latency_factor = max(0.5, min(1.0, 1.0 / latency))  # Menor latência = maior fator
            success_factor = success_rate / 100
            
            # Aplicar fatores operacionais
            score = score * success_factor * latency_factor
            
            model_scores[model_id] = score
        
        # 3. Selecionar o modelo com a maior pontuação
        if model_scores:
            best_model = max(model_scores.items(), key=lambda x: x[1])[0]
            logger.info(f"Modelo selecionado para consulta: {best_model} (pontuação: {model_scores[best_model]:.2f})")
            return best_model
        
        # Fallback para o modelo padrão
        logger.warning("Não foi possível calcular pontuações, usando modelo padrão")
        return self.router.default_model

class SmartLLMRouter:
    """
    Router inteligente para modelos LLM com seleção baseada em características da consulta,
    limitação de taxa, monitoramento e cache.
    """
    
    def __init__(self, base_router: Optional[LLMRouter] = None):
        """
        Inicializa o router inteligente.
        
        Args:
            base_router: Instância do LLMRouter base (opcional)
        """
        self.router = base_router or llm_router
        self.selector = ModelSelector(self.router)
        self.cache = get_cache()
        self.rate_limiter = get_rate_limiter()
        self.metrics = get_llm_metrics()
        
        logger.info("SmartLLMRouter inicializado")
    
    async def smart_generate(
        self, 
        prompt: str,
        model_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
        use_cache: bool = True,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Gera texto usando o modelo mais adequado, com cache e limitação de taxa.
        
        Args:
            prompt: Texto de entrada
            model_id: ID do modelo preferido (opcional)
            max_tokens: Número máximo de tokens
            temperature: Controle de aleatoriedade
            stream: Se True, retorna um gerador para streaming
            use_cache: Se True, verifica e utiliza cache
            user_id: ID do usuário (para limitação de taxa)
            **kwargs: Argumentos adicionais para geração
            
        Returns:
            Texto gerado ou gerador de streaming
        """
        # Se estiver em modo de streaming, não usar cache
        if stream:
            use_cache = False
        
        # Verificar cache se estiver ativado
        cache_key = None
        if use_cache:
            # Criar chave de cache que inclui todos os parâmetros relevantes
            params = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **{k: v for k, v in kwargs.items() if k not in ["api_key"]}
            }
            cache_key = f"llm:generate:{hash(str(params))}"
            
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                logger.info(f"Resultado encontrado no cache para prompt: {prompt[:30]}...")
                return cached_result
        
        # Verificar rate limit (se houver user_id)
        if user_id:
            is_allowed, rate_info = await self.rate_limiter.check_rate_limit(
                key=user_id,
                limit=60,  # 60 solicitações por minuto por usuário
                period=60,
                category="generate"
            )
            
            if not is_allowed:
                remaining = int(rate_info.get("reset", time.time()) - time.time())
                error_msg = f"Limite de taxa excedido. Tente novamente em {remaining} segundos."
                logger.warning(f"Rate limit atingido para usuário {user_id}: {error_msg}")
                raise Exception(error_msg)
        
        # Selecionar o melhor modelo para a consulta
        selected_model_id = await self.selector.select_best_model(
            query=prompt,
            operation="generate",
            preferred_model=model_id
        )
        
        # Registrar início da solicitação
        request_id = await self.metrics.record_request(
            model_id=selected_model_id,
            operation="generate",
            user_id=user_id,
            metadata={
                "prompt_length": len(prompt),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }
        )
        
        # Iniciar o cronômetro
        start_time = time.time()
        success = False
        error_msg = None
        result = None
        
        try:
            # Obter o modelo selecionado
            model = self.router.get_model(selected_model_id)
            
            # Gerar texto
            result = await model.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                **kwargs
            )
            
            # Se for streaming, não podemos armazenar em cache
            if not stream:
                success = True
                
                # Armazenar em cache se necessário
                if use_cache and cache_key:
                    await self.cache.set(cache_key, result, ttl=3600)  # 1 hora de TTL
            else:
                # Para streaming, precisamos de um wrapper para métricas
                async def metrics_wrapper():
                    nonlocal success
                    chunks = []
                    
                    try:
                        async for chunk in result:
                            chunks.append(chunk)
                            yield chunk
                        success = True
                    except Exception as e:
                        nonlocal error_msg
                        error_msg = str(e)
                        raise
                    finally:
                        # Registrar resposta após o streaming
                        combined_result = "".join(chunks)
                        await self.metrics.record_response(
                            request_id=request_id,
                            success=success,
                            latency=time.time() - start_time,
                            tokens=int(len(combined_result.split()) * 1.3),  # Aproximação
                            error=error_msg
                        )
                
                return metrics_wrapper()
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro na geração de texto: {error_msg}")
            raise
            
        finally:
            # Registrar resultado, exceto para streaming (que é tratado no wrapper)
            if not stream:
                # Estimar tokens para métricas (aproximado)
                tokens = None
                if isinstance(result, str):
                    tokens = int(len(result.split()) * 1.3)
                
                await self.metrics.record_response(
                    request_id=request_id,
                    success=success,
                    latency=time.time() - start_time,
                    tokens=tokens,
                    error=error_msg
                )
    
    async def smart_embed(
        self,
        text: Union[str, List[str]],
        model_id: Optional[str] = None,
        use_cache: bool = True,
        user_id: Optional[str] = None
    ) -> Union[List[float], List[List[float]]]:
        """
        Cria embeddings usando o modelo mais adequado, com cache e limitação de taxa.
        
        Args:
            text: Texto ou lista de textos
            model_id: ID do modelo preferido (opcional)
            use_cache: Se True, verifica e utiliza cache
            user_id: ID do usuário (para limitação de taxa)
            
        Returns:
            Vetor de embedding ou lista de vetores
        """
        # Verificar cache se estiver ativado
        cache_key = None
        if use_cache:
            # Criar chave de cache
            text_for_hash = text if isinstance(text, str) else str(text)
            cache_key = f"llm:embed:{hash(text_for_hash)}"
            
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                logger.info(f"Embedding encontrado no cache")
                return cached_result
        
        # Verificar rate limit (se houver user_id)
        if user_id:
            is_allowed, rate_info = await self.rate_limiter.check_rate_limit(
                key=user_id,
                limit=120,  # 120 solicitações por minuto por usuário
                period=60,
                category="embed"
            )
            
            if not is_allowed:
                remaining = int(rate_info.get("reset", time.time()) - time.time())
                error_msg = f"Limite de taxa excedido. Tente novamente em {remaining} segundos."
                logger.warning(f"Rate limit atingido para usuário {user_id}: {error_msg}")
                raise Exception(error_msg)
        
        # Simplificação: a seleção de modelo para embeddings é mais simples
        # e geralmente focada em velocidade e consistência
        query = text if isinstance(text, str) else " ".join(text[:3])
        
        selected_model_id = await self.selector.select_best_model(
            query=query,
            operation="embed",
            preferred_model=model_id
        )
        
        # Registrar início da solicitação
        request_id = await self.metrics.record_request(
            model_id=selected_model_id,
            operation="embed",
            user_id=user_id,
            metadata={
                "text_type": "single" if isinstance(text, str) else f"list[{len(text)}]"
            }
        )
        
        # Iniciar o cronômetro
        start_time = time.time()
        success = False
        error_msg = None
        result = None
        
        try:
            # Obter o modelo selecionado
            model = self.router.get_model(selected_model_id)
            
            # Criar embedding
            result = await model.embed(text=text)
            success = True
            
            # Armazenar em cache se necessário
            if use_cache and cache_key:
                await self.cache.set(cache_key, result, ttl=86400)  # 24 horas de TTL
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro na criação de embedding: {str(e)}")
            raise
            
        finally:
            # Registrar resultado
            await self.metrics.record_response(
                request_id=request_id,
                success=success,
                latency=time.time() - start_time,
                error=error_msg,
                metadata={
                    "embedding_dim": len(result[0]) if result and isinstance(result, list) and len(result) > 0 else None
                }
            )
    
    async def get_model_metrics(self, model_id: Optional[str] = None, period: str = "today") -> Dict[str, Any]:
        """
        Obtém métricas para um ou todos os modelos.
        
        Args:
            model_id: ID do modelo específico (opcional)
            period: Período ('today', 'yesterday', 'week', 'month')
            
        Returns:
            Dicionário com métricas
        """
        return await self.metrics.get_model_metrics(
            model_id=model_id,
            period=period
        )

# Singleton para acesso global ao router inteligente
_smart_router_instance = None

def get_smart_router() -> SmartLLMRouter:
    """
    Obtém a instância do router inteligente.
    
    Returns:
        Instância do SmartLLMRouter
    """
    global _smart_router_instance
    
    if _smart_router_instance is None:
        _smart_router_instance = SmartLLMRouter()
    
    return _smart_router_instance