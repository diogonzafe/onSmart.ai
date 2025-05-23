# app/main.py - Reorganizado com nova estrutura de controllers

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.database import engine, Base
from sqlalchemy import text, inspect
import logging

# CORREÇÃO: Importar todos os modelos ANTES de criar as tabelas
from app.models import *  # Isso importa todos os modelos na ordem correta

# =============================================================================
# 🔧 CONFIGURAÇÃO INICIAL
# =============================================================================

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar tabelas no banco de dados
try:
    logger.info("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas criadas com sucesso!")
except Exception as e:
    logger.error(f"Erro ao criar tabelas: {str(e)}")
    raise

# Configurar pgvector
with engine.connect() as connection:
    try:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()
        logger.info("Extensão pgvector criada/verificada com sucesso")
        
        inspector = inspect(engine)
        if "message_embeddings" in inspector.get_table_names():
            connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_message_embeddings 
            ON message_embeddings USING ivfflat (embedding vector_l2_ops);
            """))
            connection.commit()
            logger.info("Índice de vetores criado/verificado com sucesso")
            
    except Exception as e:
        logger.error(f"Erro ao configurar pgvector: {str(e)}")

# Inicializar modelos LLM
try:
    from app.llm import initialize_models_from_config
    initialize_models_from_config()
    logger.info("Modelos LLM inicializados com sucesso")
except Exception as e:
    logger.error(f"Erro ao inicializar modelos LLM: {str(e)}")

# Inicializar sistema de templates
try:
    from app.templates.base import get_template_manager
    template_manager = get_template_manager()
    logger.info("Sistema de templates inicializado com sucesso")
except Exception as e:
    logger.error(f"Erro ao inicializar sistema de templates: {str(e)}")

# =============================================================================
# 🚀 APLICAÇÃO FASTAPI
# =============================================================================

app = FastAPI(
    title="Multi-Agent AI System",
    description="Sistema Multi-Agentes de IA com Protocolo MCP",
    version="2.0.0",
    debug=settings.DEBUG
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# 📁 CONTROLLERS REORGANIZADOS POR ORDEM DE USO
# =============================================================================

# 1️⃣ CORE ENDPOINTS (Fluxo Principal)
logger.info("Registrando controllers core...")

# Autenticação e usuários
try:
    from app.api import auth, users
    app.include_router(auth.router)
    app.include_router(users.router)
    logger.info("✅ Controllers de autenticação registrados")
except ImportError as e:
    logger.error(f"❌ Erro ao importar controllers de auth: {e}")

# Templates (2º passo do fluxo)
try:
    from app.api import templates_api
    app.include_router(templates_api.router)
    logger.info("✅ Controller de templates registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar templates_api: {e}")

# Agentes (3º passo do fluxo)
try:
    from app.api import agents_api
    app.include_router(agents_api.router)
    logger.info("✅ Controller de agentes registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar agents_api: {e}")

# Conversas (4º passo do fluxo)
try:
    from app.api import conversations_api
    app.include_router(conversations_api.router)
    logger.info("✅ Controller de conversas registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar conversations_api: {e}")

# Mensagens (5º passo do fluxo - NOVO)
try:
    from app.api import messages_api
    app.include_router(messages_api.router)
    logger.info("✅ Controller de mensagens registrado")
except ImportError as e:
    logger.warning(f"⚠️ Controller de mensagens não encontrado: {e}")
    logger.info("💡 Criar app/api/messages_api.py com o conteúdo do artifacts")

# 2️⃣ SYSTEM ENDPOINTS (Funcionalidades do Sistema)
logger.info("Registrando controllers de sistema...")

# Orquestração
try:
    from app.api import orchestration_api
    app.include_router(orchestration_api.router)
    logger.info("✅ Controller de orquestração registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar orchestration_api: {e}")

# Analytics (renomeado de metrics)
try:
    from app.api import analytics_api
    app.include_router(analytics_api.router)
    logger.info("✅ Controller de analytics registrado")
except ImportError as e:
    logger.warning(f"⚠️ Controller de analytics não encontrado: {e}")
    logger.info("💡 Criar app/api/analytics_api.py ou usar metrics_api.py existente")
    
    # Fallback para metrics_api existente
    try:
        from app.api import metrics_api
        app.include_router(metrics_api.router)
        logger.info("✅ Controller de metrics (fallback) registrado")
    except ImportError:
        logger.error("❌ Nenhum controller de métricas disponível")

# LLM Management
try:
    from app.api import llm_api
    app.include_router(llm_api.router)
    logger.info("✅ Controller de LLM registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar llm_api: {e}")

# MCP Protocol
try:
    from app.api import mcp_api
    app.include_router(mcp_api.router)
    logger.info("✅ Controller de MCP registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar mcp_api: {e}")

# 3️⃣ UTILITY ENDPOINTS (Utilitários)
logger.info("Registrando controllers utilitários...")

# Operações em lote
try:
    from app.api import batch_api
    app.include_router(batch_api.router)
    logger.info("✅ Controller de batch registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar batch_api: {e}")

# Administração (NOVO)
try:
    from app.api import admin_api
    app.include_router(admin_api.router)
    logger.info("✅ Controller de admin registrado")
except ImportError as e:
    logger.warning(f"⚠️ Controller de admin não encontrado: {e}")
    logger.info("💡 Criar app/api/admin_api.py com o conteúdo do artifacts")

# Testes
try:
    from app.api import test_api
    app.include_router(test_api.router)
    logger.info("✅ Controller de test registrado")
except ImportError as e:
    logger.error(f"❌ Erro ao importar test_api: {e}")

# =============================================================================
# 🏠 ENDPOINTS RAIZ
# =============================================================================

@app.get("/")
async def root():
    return {
        "message": "Multi-Agent AI System API", 
        "version": "2.0.0",
        "description": "Sistema Multi-Agentes de IA com MCP - Versão Reorganizada",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": "2025-01-21T12:00:00Z"
    }

@app.get("/api/info")
async def api_info():
    """
    📋 Informações sobre a API reorganizada
    """
    return {
        "api_version": "2.0.0",
        "structure": {
            "core_endpoints": {
                "description": "Fluxo principal do usuário",
                "endpoints": [
                    "/api/auth/* - Autenticação e registro",
                    "/api/users/* - Gestão de usuários",
                    "/api/templates/* - Templates departamentais",
                    "/api/agents/* - Criação e gestão de agentes",
                    "/api/conversations/* - Gestão de conversas",
                    "/api/messages/* - Envio e recebimento de mensagens"
                ]
            },
            "system_endpoints": {
                "description": "Funcionalidades do sistema",
                "endpoints": [
                    "/api/orchestration/* - Orquestração de agentes",
                    "/api/analytics/* - Métricas e relatórios",
                    "/api/llm/* - Gestão de modelos LLM",
                    "/api/mcp/* - Protocolo MCP"
                ]
            },
            "utility_endpoints": {
                "description": "Utilitários e administração",
                "endpoints": [
                    "/api/batch/* - Operações em lote",
                    "/api/admin/* - Administração do sistema",
                    "/api/test/* - Testes e debugging"
                ]
            }
        },
        "flow": [
            "1. Usuário se registra (/api/auth/register)",
            "2. Cria templates (/api/templates/)",
            "3. Cria agentes (/api/agents/)",
            "4. Inicia conversas (/api/conversations/)",
            "5. Envia mensagens (/api/messages/send)",
            "6. Sistema orquestra via supervisor automaticamente"
        ]
    }

@app.get("/api/debug/routes")
async def list_api_routes():
    """
    🔍 Lista todas as rotas da API para debugging
    """
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', None)
            })
    
    # Agrupar por prefixo
    grouped_routes = {}
    for route in routes:
        path = route["path"]
        if path.startswith("/api/"):
            parts = path.split("/")
            prefix = parts[2] if len(parts) > 2 else "root"
        else:
            prefix = "root"
        
        if prefix not in grouped_routes:
            grouped_routes[prefix] = []
        
        grouped_routes[prefix].append(route)
    
    return {
        "total_routes": len(routes),
        "routes_by_controller": grouped_routes
    }

# =============================================================================
# 🎬 EVENTOS DE INICIALIZAÇÃO
# =============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("=== 🚀 INICIANDO SISTEMA MULTI-AGENTES ===")
    
    # Verificar e carregar templates padrão
    try:
        from app.db.database import SessionLocal
        from app.models.template import Template
        
        db = SessionLocal()
        template_count = db.query(Template).count()
        
        if template_count == 0:
            logger.info("Nenhum template encontrado. Carregando templates padrão...")
            
            try:
                from app.scripts.seed_templates import seed_templates
                seed_templates()
                logger.info("✅ Templates padrão carregados com sucesso")
            except ImportError:
                logger.warning("⚠️ Script de seed não encontrado. Templates padrão não carregados.")
        else:
            logger.info(f"✅ Encontrados {template_count} templates no banco de dados")
        
        db.close()
    except Exception as e:
        logger.error(f"❌ Erro durante inicialização de templates: {str(e)}")

    logger.info("=== ✅ SISTEMA MULTI-AGENTES INICIADO COM SUCESSO ===")
    logger.info("📖 Documentação disponível em: http://localhost:8000/docs")
    logger.info("ℹ️ Info da API em: http://localhost:8000/api/info")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=== 🛑 ENCERRANDO SISTEMA MULTI-AGENTES ===")
    
    # Parar serviços se necessário
    try:
        from app.llm.smart_router import get_smart_router
        smart_router = get_smart_router()
        await smart_router.shutdown()
        logger.info("✅ Smart Router encerrado")
    except Exception as e:
        logger.error(f"❌ Erro ao encerrar Smart Router: {str(e)}")
    
    logger.info("=== ✅ SISTEMA ENCERRADO ===")

# =============================================================================
# 🎯 EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("🌟 Iniciando servidor de desenvolvimento...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )