# app/api/llm_api.py
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Any, Optional, Union
import time
import logging
from pydantic import BaseModel, Field

from app.core.security import get_current_active_user
from app.models.user import User
from app.core.monitoring import get_llm_metrics
from app.core.rate_limiter import get_rate_limiter

# Configuração de logging
logger = logging.getLogger(__name__)

# Instanciar o router
router = APIRouter(prefix="/api/llm", tags=["llm"])

# Modelos de dados para a API
class GenerateRequest(BaseModel):
    prompt: str
    model_id: Optional[str] = None
    max_tokens: Optional[int] = Field(default=256, ge=1, le=4096)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=1.0)
    use_cache: bool = True

class GenerateResponse(BaseModel):
    text: str
    model_used: str
    processing_time: float
    token_estimate: Optional[int] = None
    cached: bool = False

class EmbedRequest(BaseModel):
    text: Union[str, List[str]]
    model_id: Optional[str] = None
    use_cache: bool = True

class EmbedResponse(BaseModel):
    embedding: Union[List[float], List[List[float]]]
    model_used: str
    processing_time: float
    dimensions: int
    cached: bool = False

class MetricsResponse(BaseModel):
    models: Dict[str, Any]
    total_requests: int
    success_rate: float
    avg_latency: float

# Endpoint para geração de texto
@router.post("/generate", response_model=GenerateResponse)
async def generate_text(
    request: GenerateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Gera texto usando o modelo LLM mais adequado.
    
    A seleção do modelo é feita automaticamente com base na complexidade da consulta,
    a menos que um modelo específico seja solicitado.
    """
    # Lazy import para evitar importação circular
    from app.llm.smart_router import get_smart_router
    
    # Obter instâncias dos serviços
    smart_router = get_smart_router()
    rate_limiter = get_rate_limiter()
    
    # Verificar rate limit
    is_allowed, rate_info = await rate_limiter.check_rate_limit(
        key=current_user.id,
        limit=60,  # 60 requisições por minuto
        period=60,
        category="generate"
    )
    
    if not is_allowed:
        logger.warning(f"Rate limit excedido para usuário {current_user.id}")
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Limite de taxa excedido",
                "reset_at": rate_info["reset"],
                "retry_after": int(rate_info["reset"] - time.time())
            }
        )
    
    # Processar a requisição
    start_time = time.time()
    cached = False
    
    try:
        # Gerar o texto
        result = await smart_router.smart_generate(
            prompt=request.prompt,
            model_id=request.model_id,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            use_cache=request.use_cache,
            user_id=current_user.id
        )
        
        # Estimar o número de tokens
        token_estimate = int(len(result.split()) * 1.3) if isinstance(result, str) else None
        
        # Determinar se usou cache
        processing_time = time.time() - start_time
        cached = processing_time < 0.1  # Assume que foi cache se for muito rápido
        
        # Obter o modelo utilizado (simplificado, na implementação real seria rastreado)
        model_used = request.model_id or "auto-selected"
        
        # Preparar a resposta
        response = GenerateResponse(
            text=result,
            model_used=model_used,
            processing_time=processing_time,
            token_estimate=token_estimate,
            cached=cached
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Erro na geração de texto: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro na geração de texto: {str(e)}"
        )

# Endpoint para criação de embeddings
@router.post("/embed", response_model=EmbedResponse)
async def create_embedding(
    request: EmbedRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Cria embeddings vetoriais para o texto fornecido.
    """
    # Lazy import para evitar importação circular
    from app.llm.smart_router import get_smart_router
    
    # Obter instâncias dos serviços
    smart_router = get_smart_router()
    rate_limiter = get_rate_limiter()
    
    # Verificar rate limit
    is_allowed, rate_info = await rate_limiter.check_rate_limit(
        key=current_user.id,
        limit=120,  # 120 requisições por minuto
        period=60,
        category="embed"
    )
    
    if not is_allowed:
        logger.warning(f"Rate limit excedido para usuário {current_user.id}")
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Limite de taxa excedido",
                "reset_at": rate_info["reset"],
                "retry_after": int(rate_info["reset"] - time.time())
            }
        )
    
    # Processar a requisição
    start_time = time.time()
    
    try:
        # Criar embeddings
        result = await smart_router.smart_embed(
            text=request.text,
            model_id=request.model_id,
            use_cache=request.use_cache,
            user_id=current_user.id
        )
        
        # Calcular dimensões
        dimensions = len(result[0]) if isinstance(result, list) and result else 0
        
        # Determinar se usou cache
        processing_time = time.time() - start_time
        cached = processing_time < 0.1  # Assume que foi cache se for muito rápido
        
        # Obter o modelo utilizado
        model_used = request.model_id or "auto-selected"
        
        # Preparar a resposta
        response = EmbedResponse(
            embedding=result,
            model_used=model_used,
            processing_time=processing_time,
            dimensions=dimensions,
            cached=cached
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Erro na criação de embedding: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro na criação de embedding: {str(e)}"
        )

# Endpoint para obter métricas dos modelos
@router.get("/metrics", response_model=MetricsResponse)
async def get_model_metrics(
    model_id: Optional[str] = None,
    period: str = Query("today", regex="^(today|yesterday|week|month)$"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtém métricas de desempenho dos modelos LLM.
    
    Args:
        model_id: ID do modelo específico (opcional)
        period: Período de tempo ('today', 'yesterday', 'week', 'month')
    """
    # Obter instâncias dos serviços
    metrics = get_llm_metrics()
    
    try:
        # Obter métricas
        model_metrics = await metrics.get_model_metrics(
            model_id=model_id,
            period=period
        )
        
        # Calcular métricas agregadas
        total_requests = 0
        success_count = 0
        latency_sum = 0
        latency_count = 0
        
        for model_data in model_metrics.values():
            for operation_data in model_data.values():
                requests = operation_data.get("requests", 0)
                successes = operation_data.get("successes", 0)
                latency = operation_data.get("latency_avg", 0)
                
                total_requests += requests
                success_count += successes
                
                if latency > 0:
                    latency_sum += latency
                    latency_count += 1
        
        # Calcular médias
        success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0
        avg_latency = latency_sum / latency_count if latency_count > 0 else 0
        
        # Preparar a resposta
        response = MetricsResponse(
            models=model_metrics,
            total_requests=total_requests,
            success_rate=success_rate,
            avg_latency=avg_latency
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao obter métricas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter métricas: {str(e)}"
        )

# Endpoint para listar modelos disponíveis
@router.get("/models")
async def list_models(
    current_user: User = Depends(get_current_active_user)
):
    """
    Lista todos os modelos LLM disponíveis e suas capacidades.
    """
    try:
        # Lazy import para evitar importação circular
        from app.llm.smart_router import get_smart_router
        
        # Obter o router
        smart_router = get_smart_router()
        
        # Lista de modelos
        models = smart_router.router.list_models()
        
        # Adicionar informações de disponibilidade
        rate_limits = await smart_router.selector.check_rate_limits()
        
        for model in models:
            model_id = model["model_id"]
            model["available"] = rate_limits.get(model_id, True)
        
        return {
            "models": models,
            "default_model": smart_router.router.default_model
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar modelos: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar modelos: {str(e)}"
        )

# Endpoint para resetar rate limit
@router.post("/reset-rate-limit")
async def reset_rate_limit(
    current_user: User = Depends(get_current_active_user)
):
    """
    Reseta o rate limit para o usuário atual.
    Disponível apenas para fins de teste/desenvolvimento.
    """
    # Obter instância do rate limiter
    rate_limiter = get_rate_limiter()
    
    try:
        # Resetar para as categorias principais
        categories = ["generate", "embed"]
        
        for category in categories:
            await rate_limiter.reset_rate_limit(
                key=current_user.id,
                category=category
            )
        
        return {
            "message": "Rate limits resetados com sucesso",
            "user_id": current_user.id
        }
        
    except Exception as e:
        logger.error(f"Erro ao resetar rate limit: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao resetar rate limit: {str(e)}"
        )