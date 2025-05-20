# app/templates/base.py
from typing import Dict, List, Any, Optional, Union
import logging
import json
import re
from datetime import datetime

from app.models.template import Template, TemplateDepartment

logger = logging.getLogger(__name__)

class TemplateManager:
    """
    Gerenciador de templates para agentes.
    Responsável por carregar, validar, versionar e renderizar templates.
    """
    
    def __init__(self):
        """Inicializa o gerenciador de templates."""
        self.template_cache: Dict[str, Dict[str, Any]] = {}  # Cache de templates
        self.template_versions: Dict[str, List[Dict[str, Any]]] = {}  # Histórico de versões
        
        # Mapeamento de variaveis para funções de validação
        self.validators = {
            "name": self._validate_string,
            "email": self._validate_email,
            "number": self._validate_number,
            "choice": self._validate_choice,
            "date": self._validate_date
        }
        
        logger.info("Gerenciador de templates inicializado")
    
    def load_template(self, template: Template) -> Dict[str, Any]:
        """
        Carrega um template do banco de dados e o prepara para uso.
        
        Args:
            template: Objeto Template do banco de dados
            
        Returns:
            Template processado e pronto para uso
        """
        template_id = template.id
        
        # Verificar se já está no cache
        if template_id in self.template_cache:
            logger.debug(f"Template {template_id} carregado do cache")
            return self.template_cache[template_id]
        
        # Processar o template
        processed_template = {
            "id": template_id,
            "name": template.name,
            "description": template.description,
            "department": template.department.value,
            "prompt_template": template.prompt_template,
            "tools_config": template.tools_config,
            "llm_config": template.llm_config,
            "variables": self._extract_variables(template.prompt_template),
            "created_at": template.created_at,
            "updated_at": template.updated_at,
            "version": 1  # Versão inicial
        }
        
        # Adicionar ao cache
        self.template_cache[template_id] = processed_template
        
        # Inicializar histórico de versões
        if template_id not in self.template_versions:
            self.template_versions[template_id] = [processed_template.copy()]
        
        logger.info(f"Template {template.name} ({template_id}) carregado com {len(processed_template['variables'])} variáveis")
        return processed_template
    
    def render_template(self, 
                      template_id: str, 
                      variables: Dict[str, Any],
                      validate: bool = True) -> str:
        """
        Renderiza um template com as variáveis fornecidas.
        
        Args:
            template_id: ID do template a ser renderizado
            variables: Dicionário com valores das variáveis
            validate: Se deve validar as variáveis antes de renderizar
            
        Returns:
            Template renderizado
        """
        if template_id not in self.template_cache:
            raise ValueError(f"Template {template_id} não encontrado no cache")
        
        template = self.template_cache[template_id]
        prompt_template = template["prompt_template"]
        
        # Validar variáveis
        if validate:
            self._validate_variables(template["variables"], variables)
        
        # Substituir variáveis no template
        rendered_template = prompt_template
        
        for var_name, var_info in template["variables"].items():
            placeholder = f"{{{{{var_name}}}}}"
            value = variables.get(var_name, var_info.get("default", ""))
            
            # Converter para string se necessário
            if not isinstance(value, str):
                value = str(value)
            
            rendered_template = rendered_template.replace(placeholder, value)
        
        logger.debug(f"Template {template_id} renderizado com sucesso")
        return rendered_template
    
    def update_template(self, 
                      template: Template, 
                      update_cache: bool = True) -> Dict[str, Any]:
        """
        Atualiza um template no cache e no histórico de versões.
        
        Args:
            template: Novo objeto Template
            update_cache: Se deve atualizar o cache
            
        Returns:
            Template atualizado
        """
        template_id = template.id
        
        # Verificar se o template existe no cache
        if template_id in self.template_cache and update_cache:
            # Incrementar versão
            current_version = self.template_cache[template_id]["version"]
            
            # Processar o template atualizado
            updated_template = {
                "id": template_id,
                "name": template.name,
                "description": template.description,
                "department": template.department.value,
                "prompt_template": template.prompt_template,
                "tools_config": template.tools_config,
                "llm_config": template.llm_config,
                "variables": self._extract_variables(template.prompt_template),
                "created_at": template.created_at,
                "updated_at": template.updated_at,
                "version": current_version + 1
            }
            
            # Atualizar cache
            self.template_cache[template_id] = updated_template
            
            # Adicionar ao histórico de versões
            if template_id in self.template_versions:
                self.template_versions[template_id].append(updated_template.copy())
            else:
                self.template_versions[template_id] = [updated_template.copy()]
            
            logger.info(f"Template {template.name} ({template_id}) atualizado para versão {current_version + 1}")
            return updated_template
        
        # Se não estiver no cache ou não for para atualizar, carregar como novo
        return self.load_template(template)
    
    def get_template_version(self, template_id: str, version: int) -> Optional[Dict[str, Any]]:
        """
        Obtém uma versão específica de um template.
        
        Args:
            template_id: ID do template
            version: Número da versão
            
        Returns:
            Template na versão especificada ou None se não encontrado
        """
        if template_id not in self.template_versions:
            return None
        
        versions = self.template_versions[template_id]
        
        # Versão 0 significa a mais recente
        if version == 0 and versions:
            return versions[-1]
        
        # Procurar pela versão específica
        for template_version in versions:
            if template_version["version"] == version:
                return template_version
        
        return None
    
    def _extract_variables(self, prompt_template: str) -> Dict[str, Dict[str, Any]]:
        """
        Extrai variáveis e seus metadados do template.
        
        Args:
            prompt_template: Texto do template
            
        Returns:
            Dicionário com informações das variáveis
        """
        variables = {}
        
        # Padrão para encontrar variáveis: {{nome_variavel}}
        # E variáveis com tipo: {{nome_variavel:tipo}}
        # E variáveis com tipo e padrão: {{nome_variavel:tipo=padrão}}
        pattern = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-zA-Z_]+)(?:=([^}]+))?)?\}\}'
        
        for match in re.finditer(pattern, prompt_template):
            var_name = match.group(1)
            var_type = match.group(2) or "string"
            var_default = match.group(3) or ""
            
            variables[var_name] = {
                "type": var_type,
                "default": var_default,
                "required": not var_default
            }
        
        return variables
    
    def _validate_variables(self, 
                          variable_specs: Dict[str, Dict[str, Any]], 
                          variables: Dict[str, Any]) -> None:
        """
        Valida as variáveis fornecidas contra as especificações.
        
        Args:
            variable_specs: Especificações das variáveis
            variables: Valores das variáveis
            
        Raises:
            ValueError: Se alguma variável não estiver de acordo com a especificação
        """
        errors = []
        
        for var_name, var_spec in variable_specs.items():
            # Verificar variáveis obrigatórias
            if var_spec["required"] and var_name not in variables:
                errors.append(f"Variável obrigatória '{var_name}' não fornecida")
                continue
            
            # Se a variável foi fornecida, validar o tipo
            if var_name in variables:
                var_type = var_spec["type"]
                var_value = variables[var_name]
                
                # Usar validador específico se disponível
                validator = self.validators.get(var_type, self._validate_string)
                try:
                    validator(var_value, var_spec)
                except ValueError as e:
                    errors.append(f"Erro na variável '{var_name}': {str(e)}")
        
        if errors:
            raise ValueError(f"Erros de validação: {', '.join(errors)}")
    
    def _validate_string(self, value: Any, spec: Dict[str, Any]) -> None:
        """Valida uma string."""
        if not isinstance(value, str):
            raise ValueError(f"Esperado string, recebido {type(value).__name__}")
    
    def _validate_email(self, value: Any, spec: Dict[str, Any]) -> None:
        """Valida um email."""
        if not isinstance(value, str):
            raise ValueError(f"Esperado string, recebido {type(value).__name__}")
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValueError("Email inválido")
    
    def _validate_number(self, value: Any, spec: Dict[str, Any]) -> None:
        """Valida um número."""
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Esperado número, recebido {type(value).__name__}")
    
    def _validate_choice(self, value: Any, spec: Dict[str, Any]) -> None:
        """Valida uma escolha entre opções."""
        if "choices" not in spec:
            return
        
        choices = spec["choices"]
        if value not in choices:
            raise ValueError(f"Valor deve ser um dos: {', '.join(choices)}")
    
    def _validate_date(self, value: Any, spec: Dict[str, Any]) -> None:
        """Valida uma data."""
        if not isinstance(value, str):
            raise ValueError(f"Esperado string de data, recebido {type(value).__name__}")
        
        date_formats = [
            r'\d{4}-\d{2}-\d{2}',  # ISO: YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # DD/MM/YYYY
            r'\d{2}-\d{2}-\d{4}'   # DD-MM-YYYY
        ]
        
        if not any(re.match(pattern, value) for pattern in date_formats):
            raise ValueError("Formato de data inválido")


# Singleton para acesso global
_template_manager = None

def get_template_manager() -> TemplateManager:
    """
    Obtém a instância do gerenciador de templates.
    
    Returns:
        Instância do TemplateManager
    """
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    
    return _template_manager