# app/main.py - Versão corrigida com imports corretos
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import orchestration_api
from app.api import auth, users
from app.db.database import engine, Base

# CORREÇÃO: Importar todos os modelos ANTES de criar as tabelas
# Isso garante que todos os relacionamentos sejam resolvidos corretamente
from app.models import *  # Isso importa todos os modelos na ordem correta

from app.api import mcp_api, agents_api
from sqlalchemy import text, inspect
from app.api import llm_api
from app.llm import initialize_models_from_config
import logging

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORREÇÃO: Agora criar todas as tabelas após importar todos os modelos
try:
    logger.info("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas criadas com sucesso!")
except Exception as e:
    logger.error(f"Erro ao criar tabelas: {str(e)}")
    raise

# Inicializar pgvector e criar o índice depois que as tabelas forem criadas
with engine.connect() as connection:
    try:
        # Criar a extensão vector
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()
        logger.info("Extensão pgvector criada/verificada com sucesso")
        
        # Verificar se a tabela message_embeddings existe antes de criar o índice
        inspector = inspect(engine)
        if "message_embeddings" in inspector.get_table_names():
            connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_message_embeddings 
            ON message_embeddings USING ivfflat (embedding vector_l2_ops);
            """))
            connection.commit()
            logger.info("Índice de vetores criado/verificado com sucesso")
        else:
            logger.warning("Tabela message_embeddings não existe. Índice será criado quando a tabela for criada.")
            
    except Exception as e:
        logger.error(f"Erro ao configurar pgvector: {str(e)}")

# Inicializar modelos LLM
try:
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

app = FastAPI(
    title=settings.APP_NAME,
    description="API para sistema multi-agentes de IA utilizando Model Context Protocol",
    version="1.0.0",
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

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(llm_api.router)
app.include_router(mcp_api.router)
app.include_router(agents_api.router)
app.include_router(orchestration_api.router)
app.include_router(
    agents_api.router,
    prefix="/api",
    tags=["agents"]
)

# Criar e incluir os novos routers
templates_router = APIRouter(prefix="/api/templates", tags=["templates"])
conversations_router = APIRouter(prefix="/api/conversations", tags=["conversations"])
metrics_router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# Importar e incluir os routers (se os arquivos existirem)
try:
    from app.api import templates_api
    app.include_router(templates_api.router)
    logger.info("Router templates_api incluído com sucesso")
except ImportError:
    app.include_router(templates_router)
    logger.warning("Módulo templates_api não encontrado. Usando router padrão.")

try:
    from app.api import conversations_api
    app.include_router(conversations_api.router)
    logger.info("Router conversations_api incluído com sucesso")
except ImportError:
    app.include_router(conversations_router)
    logger.warning("Módulo conversations_api não encontrado. Usando router padrão.")

try:
    from app.api import metrics_api
    app.include_router(metrics_api.router)
    logger.info("Router metrics_api incluído com sucesso")
except ImportError:
    app.include_router(metrics_router)
    logger.warning("Módulo metrics_api não encontrado. Usando router padrão.")

@app.get("/")
async def root():
    return {
        "message": "Multi-Agent AI System API", 
        "version": "1.0.0",
        "description": "Sistema de múltiplos agentes de IA com integração MCP"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/debug/endpoints")
async def list_endpoints():
    """Lista todos os endpoints registrados para depuração."""
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, "methods") else None
        })
    return {"routes": routes}

# Evento de inicialização da aplicação
@app.on_event("startup")
async def startup_event():
    logger.info("=== Iniciando aplicação ===")
    
    # Verificar se deve carregar templates padrão
    try:
        from app.db.database import SessionLocal
        from app.models.template import Template
        
        db = SessionLocal()
        template_count = db.query(Template).count()
        
        if template_count == 0:
            logger.info("Nenhum template encontrado. Carregando templates padrão...")
            
            # Importar e executar o script de seed
            from app.scripts.seed_templates import seed_templates
            seed_templates()
            
            logger.info("Templates padrão carregados com sucesso")
        else:
            logger.info(f"Encontrados {template_count} templates no banco de dados")
        
        db.close()
    except Exception as e:
        logger.error(f"Erro durante inicialização de templates: {str(e)}")

    logger.info("=== Aplicação iniciada com sucesso ===")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)