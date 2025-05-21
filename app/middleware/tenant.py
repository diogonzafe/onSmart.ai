# app/middleware/tenant.py
from fastapi import Request, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.database import get_db
from app.models.organization import Organization
from app.core.security import get_current_user

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extrair tenant do header ou do usuário autenticado
        tenant_header = request.headers.get("X-Tenant-ID")
        
        if tenant_header:
            request.state.tenant_id = tenant_header
        else:
            # Tentar obter do usuário autenticado (se for o caso)
            try:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    db = next(get_db())
                    user = await get_current_user(auth_header.replace("Bearer ", ""), db)
                    if user and user.organization_id:
                        request.state.tenant_id = user.organization_id
            except:
                # Se falhar, não define tenant_id
                pass
        
        # Continuar com o request
        response = await call_next(request)
        return response

# app/main.py - Adicionar o middleware
from app.middleware.tenant import TenantMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(TenantMiddleware)