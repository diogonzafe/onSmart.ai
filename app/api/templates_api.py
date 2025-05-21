# app/api/templates_api.py
from fastapi import APIRouter, Depends, HTTPException, Body, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.db.database import get_db
from app.models.user import User
from app.models.template import Template, TemplateDepartment
from app.core.security import get_current_active_user
from app.schemas.template import TemplateCreate, TemplateUpdate, Template as TemplateSchema
from app.services.template_service import get_template_service

router = APIRouter(prefix="/api/templates", tags=["templates"])

@router.get("/", response_model=List[TemplateSchema])
async def list_templates(
    department: Optional[TemplateDepartment] = None,
    public_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Lista templates disponíveis para o usuário."""
    template_service = get_template_service(db)
    
    templates = template_service.list_templates(
        user_id=None if public_only else current_user.id,
        department=department,
        is_public=True if public_only else None
    )
    
    return templates

@router.get("/{template_id}", response_model=TemplateSchema)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtém detalhes de um template específico."""
    template_service = get_template_service(db)
    
    try:
        template = template_service.get_template(template_id)
        
        # Verificar permissão - template público ou pertencente ao usuário
        if not template.is_public and template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Acesso negado a este template")
        
        return template
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/", response_model=TemplateSchema)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cria um novo template."""
    template_service = get_template_service(db)
    
    try:
        template = template_service.create_template(
            name=template_data.name,
            description=template_data.description,
            department=template_data.department,
            is_public=template_data.is_public,
            user_id=current_user.id,
            prompt_template=template_data.prompt_template,
            tools_config=template_data.tools_config,
            llm_config=template_data.llm_config
        )
        
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{template_id}", response_model=TemplateSchema)
async def update_template(
    template_id: str,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Atualiza um template existente."""
    template_service = get_template_service(db)
    
    # Verificar se o template pertence ao usuário
    try:
        existing_template = template_service.get_template(template_id)
        if existing_template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Acesso negado a este template")
    except ValueError:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    
    # Atualizar template
    try:
        updated_template = template_service.update_template(
            template_id=template_id,
            name=template_data.name,
            description=template_data.description,
            department=template_data.department,
            is_public=template_data.is_public,
            prompt_template=template_data.prompt_template,
            tools_config=template_data.tools_config,
            llm_config=template_data.llm_config
        )
        
        return updated_template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Remove um template."""
    template_service = get_template_service(db)
    
    # Verificar se o template pertence ao usuário
    try:
        existing_template = template_service.get_template(template_id)
        if existing_template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Acesso negado a este template")
    except ValueError:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    
    # Remover template
    result = template_service.delete_template(template_id)
    
    if result:
        return {"message": "Template removido com sucesso"}
    else:
        raise HTTPException(status_code=400, detail="Não foi possível remover o template")

@router.get("/{template_id}/variables")
async def get_template_variables(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtém as variáveis de um template."""
    template_service = get_template_service(db)
    
    try:
        # Verificar acesso ao template
        template = template_service.get_template(template_id)
        if not template.is_public and template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Acesso negado a este template")
        
        # Obter variáveis
        variables = template_service.get_template_variables(template_id)
        return variables
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
# app/api/templates_api.py - Adicionar endpoints

@router.post("/preview")
async def preview_template(
    template_data: Dict[str, Any] = Body(...),
    variables: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Gera um preview de um template sem salvá-lo."""
    template_service = get_template_service(db)
    
    try:
        preview = template_service.preview_template(template_data, variables)
        return {"preview": preview}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{template_id}/draft")
async def create_draft(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cria um rascunho a partir de um template existente."""
    template_service = get_template_service(db)
    
    try:
        draft = template_service.create_draft_from_template(
            template_id=template_id,
            user_id=current_user.id
        )
        return draft
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{draft_id}/publish")
async def publish_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Publica um rascunho."""
    template_service = get_template_service(db)
    
    try:
        published = template_service.publish_draft(draft_id)
        return published
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))    