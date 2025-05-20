# app/services/template_service.py
from typing import Dict, List, Any, Optional, Union
import logging
from sqlalchemy.orm import Session
import uuid

from app.models.template import Template, TemplateDepartment
from app.templates.base import get_template_manager

logger = logging.getLogger(__name__)

class TemplateService:
    """
    Serviço para gerenciamento de templates.
    Fornece funcionalidades para criar, atualizar, listar e gerenciar versões de templates.
    """
    
    def __init__(self, db: Session):
        """
        Inicializa o serviço de templates.
        
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self.template_manager = get_template_manager()
    
    def create_template(self, 
                      name: str, 
                      department: TemplateDepartment, 
                      prompt_template: str, 
                      description: Optional[str] = None, 
                      is_public: bool = False,
                      user_id: Optional[str] = None,
                      tools_config: Optional[Dict[str, Any]] = None,
                      llm_config: Optional[Dict[str, Any]] = None) -> Template:
        """
        Cria um novo template.
        
        Args:
            name: Nome do template
            department: Departamento do template
            prompt_template: Texto do template com placeholders para variáveis
            description: Descrição do template (opcional)
            is_public: Se o template é público
            user_id: ID do usuário proprietário (opcional para templates do sistema)
            tools_config: Configuração de ferramentas (opcional)
            llm_config: Configuração do LLM (opcional)
            
        Returns:
            Instância do template criado
        """
        # Verificar se as variáveis do template são válidas
        try:
            variables = self.template_manager._extract_variables(prompt_template)
        except Exception as e:
            logger.error(f"Erro ao extrair variáveis do template: {str(e)}")
            raise ValueError(f"Template inválido: {str(e)}")
        
        # Criar o template
        template = Template(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            department=department,
            is_public=is_public,
            user_id=user_id,
            prompt_template=prompt_template,
            tools_config=tools_config or {},
            llm_config=llm_config or {}
        )
        
        # Salvar no banco de dados
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        # Carregar no gerenciador de templates
        self.template_manager.load_template(template)
        
        logger.info(f"Template criado: {name} ({template.id})")
        return template
    
    def update_template(self, 
                      template_id: str, 
                      name: Optional[str] = None, 
                      description: Optional[str] = None, 
                      department: Optional[TemplateDepartment] = None,
                      is_public: Optional[bool] = None,
                      prompt_template: Optional[str] = None,
                      tools_config: Optional[Dict[str, Any]] = None,
                      llm_config: Optional[Dict[str, Any]] = None) -> Template:
        """
        Atualiza um template existente.
        
        Args:
            template_id: ID do template a ser atualizado
            name: Novo nome (opcional)
            description: Nova descrição (opcional)
            department: Novo departamento (opcional)
            is_public: Novo status público (opcional)
            prompt_template: Novo texto do template (opcional)
            tools_config: Nova configuração de ferramentas (opcional)
            llm_config: Nova configuração do LLM (opcional)
            
        Returns:
            Template atualizado
        """
        # Buscar o template
        template = self.db.query(Template).filter(Template.id == template_id).first()
        if not template:
            logger.error(f"Template {template_id} não encontrado")
            raise ValueError(f"Template {template_id} não encontrado")
        
        # Atualizar campos
        if name is not None:
            template.name = name
        
        if description is not None:
            template.description = description
        
        if department is not None:
            template.department = department
        
        if is_public is not None:
            template.is_public = is_public
        
        if prompt_template is not None:
            # Verificar se as variáveis do template são válidas
            try:
                variables = self.template_manager._extract_variables(prompt_template)
            except Exception as e:
                logger.error(f"Erro ao extrair variáveis do template: {str(e)}")
                raise ValueError(f"Template inválido: {str(e)}")
            
            template.prompt_template = prompt_template
        
        if tools_config is not None:
            template.tools_config = tools_config
        
        if llm_config is not None:
            template.llm_config = llm_config
        
        # Aplicar as alterações
        self.db.commit()
        self.db.refresh(template)
        
        # Atualizar no gerenciador de templates
        self.template_manager.update_template(template)
        
        logger.info(f"Template atualizado: {template.name} ({template_id})")
        return template
    
    def get_template(self, template_id: str) -> Template:
        """
        Obtém um template pelo ID.
        
        Args:
            template_id: ID do template
            
        Returns:
            Instância do template
        """
        template = self.db.query(Template).filter(Template.id == template_id).first()
        if not template:
            logger.error(f"Template {template_id} não encontrado")
            raise ValueError(f"Template {template_id} não encontrado")
        
        return template
    
    def list_templates(self, 
                     user_id: Optional[str] = None, 
                     department: Optional[TemplateDepartment] = None, 
                     is_public: Optional[bool] = None) -> List[Template]:
        """
        Lista templates com filtros.
        
        Args:
            user_id: ID do usuário proprietário (opcional)
            department: Filtro por departamento (opcional)
            is_public: Filtro por status público (opcional)
            
        Returns:
            Lista de templates
        """
        query = self.db.query(Template)
        
        if user_id:
            query = query.filter(Template.user_id == user_id)
        
        if department:
            query = query.filter(Template.department == department)
        
        if is_public is not None:
            query = query.filter(Template.is_public == is_public)
        
        return query.all()
    
    def delete_template(self, template_id: str) -> bool:
        """
        Remove um template.
        
        Args:
            template_id: ID do template
            
        Returns:
            True se bem-sucedido, False caso contrário
        """
        template = self.db.query(Template).filter(Template.id == template_id).first()
        if not template:
            logger.error(f"Template {template_id} não encontrado")
            return False
        
        # Verificar se existem agentes usando este template
        from app.models.agent import Agent
        agent_count = self.db.query(Agent).filter(Agent.template_id == template_id).count()
        
        if agent_count > 0:
            logger.error(f"Não é possível excluir o template {template_id} pois existem {agent_count} agentes utilizando-o")
            return False
        
        # Remover do banco de dados
        self.db.delete(template)
        self.db.commit()
        
        logger.info(f"Template removido: {template.name} ({template_id})")
        return True
    
    def get_template_version(self, template_id: str, version: int = 0) -> Dict[str, Any]:
        """
        Obtém uma versão específica de um template.
        
        Args:
            template_id: ID do template
            version: Número da versão (0 = mais recente)
            
        Returns:
            Versão do template
        """
        # Verificar se o template existe
        template = self.get_template(template_id)
        
        # Carregar no gerenciador se ainda não estiver
        if template_id not in self.template_manager.template_cache:
            self.template_manager.load_template(template)
        
        # Obter a versão solicitada
        template_version = self.template_manager.get_template_version(template_id, version)
        
        if not template_version:
            if version == 0:
                logger.error(f"Template {template_id} não encontrado no cache")
                raise ValueError(f"Template {template_id} não encontrado no cache")
            else:
                logger.error(f"Versão {version} do template {template_id} não encontrada")
                raise ValueError(f"Versão {version} do template {template_id} não encontrada")
        
        return template_version
    
    def render_template(self, 
                      template_id: str, 
                      variables: Dict[str, Any], 
                      validate: bool = True) -> str:
        """
        Renderiza um template com as variáveis fornecidas.
        
        Args:
            template_id: ID do template
            variables: Dicionário com valores das variáveis
            validate: Se deve validar as variáveis antes de renderizar
            
        Returns:
            Template renderizado
        """
        # Verificar se o template existe
        template = self.get_template(template_id)
        
        # Carregar no gerenciador se ainda não estiver
        if template_id not in self.template_manager.template_cache:
            self.template_manager.load_template(template)
        
        # Renderizar o template
        try:
            rendered = self.template_manager.render_template(
                template_id, variables, validate
            )
            return rendered
        except ValueError as e:
            logger.error(f"Erro ao renderizar template {template_id}: {str(e)}")
            raise
    
    def get_template_variables(self, template_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Obtém as variáveis de um template.
        
        Args:
            template_id: ID do template
            
        Returns:
            Dicionário com informações das variáveis
        """
        # Verificar se o template existe
        template = self.get_template(template_id)
        
        # Carregar no gerenciador se ainda não estiver
        if template_id not in self.template_manager.template_cache:
            self.template_manager.load_template(template)
        
        template_cache = self.template_manager.template_cache.get(template_id)
        if not template_cache:
            logger.error(f"Template {template_id} não encontrado no cache")
            raise ValueError(f"Template {template_id} não encontrado no cache")
        
        return template_cache.get("variables", {})

# Singleton para acesso global
_template_service_instance = None

def get_template_service(db: Session) -> TemplateService:
    """
    Obtém ou cria a instância do serviço de templates.
    
    Args:
        db: Sessão do banco de dados
        
    Returns:
        Instância do TemplateService
    """
    global _template_service_instance
    
    if _template_service_instance is None:
        _template_service_instance = TemplateService(db)
    
    return _template_service_instance