#!/bin/bash

# Script para executar os testes com as configurações corretas

# Verificar se estamos na pasta correta
if [ ! -d "app" ]; then
    echo "Erro: Execute este script da pasta backend/ (onde está a pasta app/)"
    exit 1
fi

# Definir variáveis de ambiente para testes
export PYTEST_CURRENT_TEST=1
export SECRET_KEY="test-secret-key-for-testing-only"
export DB_NAME="test_onsmart"
export REDIS_URL="redis://localhost:6379/1"

# Adicionar o diretório atual ao PYTHONPATH para que 'app' seja encontrado
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Executar os testes
echo "Executando testes unitários..."
python -m pytest app/tests/newtest -v --tb=short

# Limpar variáveis de ambiente
unset PYTEST_CURRENT_TEST
unset SECRET_KEY
unset DB_NAME
unset REDIS_URL

echo "Testes concluídos!"