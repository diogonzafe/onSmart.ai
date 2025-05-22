#!/usr/bin/env python3
# app/scripts/migrate_organizations.py
"""
Script para migrar o banco de dados e adicionar a tabela organizations
"""

import os
import sys
import logging

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy import create_engine, text
from app.config import settings

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Executa a migração do banco de dados."""
    
    # Conectar ao banco de dados
    engine = create_engine(settings.DATABASE_URL)
    
    # SQL da migração
    migration_sql = """
    -- 1. Criar tabela organizations
    CREATE TABLE IF NOT EXISTS organizations (
        id VARCHAR PRIMARY KEY,
        name VARCHAR NOT NULL,
        slug VARCHAR UNIQUE NOT NULL,
        settings JSONB NOT NULL DEFAULT '{}',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- 2. Verificar se a coluna organization_id já existe na tabela users
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'organization_id'
        ) THEN
            ALTER TABLE users ADD COLUMN organization_id VARCHAR;
            ALTER TABLE users ADD CONSTRAINT fk_users_organization 
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL;
        END IF;
    END $$;

    -- 3. Verificar se a coluna organization_id já existe na tabela agents
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'agents' AND column_name = 'organization_id'
        ) THEN
            ALTER TABLE agents ADD COLUMN organization_id VARCHAR;
            ALTER TABLE agents ADD CONSTRAINT fk_agents_organization 
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL;
        END IF;
    END $$;

    -- 4. Verificar se a coluna organization_id já existe na tabela templates
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'templates' AND column_name = 'organization_id'
        ) THEN
            ALTER TABLE templates ADD COLUMN organization_id VARCHAR;
            ALTER TABLE templates ADD CONSTRAINT fk_templates_organization 
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL;
        END IF;
    END $$;

    -- 5. Verificar se a coluna organization_id já existe na tabela tools
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'tools' AND column_name = 'organization_id'
        ) THEN
            ALTER TABLE tools ADD COLUMN organization_id VARCHAR;
            ALTER TABLE tools ADD CONSTRAINT fk_tools_organization 
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL;
        END IF;
    END $$;

    -- 6. Criar índices para performance
    CREATE INDEX IF NOT EXISTS idx_users_organization ON users(organization_id);
    CREATE INDEX IF NOT EXISTS idx_agents_organization ON agents(organization_id);
    CREATE INDEX IF NOT EXISTS idx_templates_organization ON templates(organization_id);
    CREATE INDEX IF NOT EXISTS idx_tools_organization ON tools(organization_id);
    """
    
    try:
        with engine.connect() as connection:
            logger.info("Iniciando migração do banco de dados...")
            
            # Executar a migração em uma transação
            with connection.begin():
                connection.execute(text(migration_sql))
            
            logger.info("Migração executada com sucesso!")
            
            # Criar organização padrão se não existir
            default_org_sql = """
            INSERT INTO organizations (id, name, slug, settings, is_active) 
            VALUES (
                'org-' || substr(md5(random()::text), 1, 8),
                'Organização Padrão',
                'organizacao-padrao',
                '{"default": true}',
                true
            ) ON CONFLICT (slug) DO NOTHING;
            """
            
            with connection.begin():
                connection.execute(text(default_org_sql))
            
            logger.info("Organização padrão criada/verificada!")
            
            # Verificar o resultado
            result = connection.execute(text("SELECT name FROM organizations LIMIT 1;")).fetchone()
            if result:
                logger.info(f"Organização encontrada: {result[0]}")
            
            logger.info("Migração concluída com sucesso!")
            
    except Exception as e:
        logger.error(f"Erro durante a migração: {str(e)}")
        raise

def check_database_status():
    """Verifica o status atual do banco de dados."""
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Verificar se a tabela organizations existe
            org_check = connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'organizations'
                );
            """)).fetchone()
            
            if org_check[0]:
                logger.info("✓ Tabela organizations existe")
                
                # Contar registros
                count = connection.execute(text("SELECT COUNT(*) FROM organizations;")).fetchone()
                logger.info(f"  - Registros: {count[0]}")
            else:
                logger.info("✗ Tabela organizations NÃO existe")
            
            # Verificar colunas organization_id
            tables_to_check = ['users', 'agents', 'templates', 'tools']
            
            for table in tables_to_check:
                column_check = connection.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'organization_id'
                    );
                """)).fetchone()
                
                if column_check[0]:
                    logger.info(f"✓ Coluna organization_id existe na tabela {table}")
                else:
                    logger.info(f"✗ Coluna organization_id NÃO existe na tabela {table}")
    
    except Exception as e:
        logger.error(f"Erro ao verificar status do banco: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migração para adicionar Organizations')
    parser.add_argument('--check', action='store_true', help='Apenas verificar o status atual')
    parser.add_argument('--migrate', action='store_true', help='Executar a migração')
    
    args = parser.parse_args()
    
    if args.check:
        logger.info("=== VERIFICANDO STATUS DO BANCO ===")
        check_database_status()
    elif args.migrate:
        logger.info("=== EXECUTANDO MIGRAÇÃO ===")
        run_migration()
    else:
        logger.info("=== VERIFICANDO STATUS E EXECUTANDO MIGRAÇÃO ===")
        check_database_status()
        print("\n" + "="*50 + "\n")
        run_migration()
