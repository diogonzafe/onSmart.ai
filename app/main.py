from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import auth, users
from app.db.database import engine, Base
from sqlalchemy import text, inspect
from app.api import llm_api
from app.llm import initialize_models_from_config  # Importa a função de inicialização

# Criar todas as tabelas primeiro
Base.metadata.create_all(bind=engine)

# Inicializar pgvector e criar o índice apenas depois que as tabelas forem criadas
with engine.connect() as connection:
    # Criar a extensão vector
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    connection.commit()
    
    # Verificar se a tabela message_embeddings existe antes de criar o índice
    inspector = inspect(engine)
    if "message_embeddings" in inspector.get_table_names():
        connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_message_embeddings 
        ON message_embeddings USING ivfflat (embedding vector_l2_ops);
        """))
        connection.commit()
        print("Índice de vetores criado com sucesso.")
    else:
        print("Tabela message_embeddings ainda não existe. O índice será criado na próxima execução.")

# Inicializar modelos LLM
initialize_models_from_config()  # Inicializa os modelos LLM

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
app.include_router(llm_api.router)  # Incluir o router LLM API

# Comentado até que os módulos sejam criados
# app.include_router(agents.router)
# app.include_router(templates.router)
# app.include_router(conversations.router)
# app.include_router(tools.router)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)