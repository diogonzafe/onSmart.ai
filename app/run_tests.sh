#!/bin/bash

# Script para executar os testes com as configurações corretas

# Verificar se estamos na pasta correta
if [ ! -d "app" ]; then
    echo "Erro: Execute este script da pasta backend/ (onde está a pasta app/)"
    exit 1
fi

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Configurando ambiente de testes ===${NC}"

# Definir variáveis de ambiente para testes
export PYTEST_CURRENT_TEST=1
export SECRET_KEY="test-secret-key-for-testing-only"
export DB_NAME="test_onsmart"
export REDIS_URL="redis://localhost:6379/1"
export DEBUG="true"

# Adicionar o diretório atual ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo -e "${GREEN}✓ Variáveis de ambiente configuradas${NC}"
echo -e "${GREEN}✓ PYTHONPATH configurado: $(pwd)${NC}"

# Função para executar testes específicos
run_specific_tests() {
    echo -e "\n${YELLOW}=== Executando testes específicos que falharam ===${NC}"
    
    echo -e "\n${YELLOW}1. Testando agent_state...${NC}"
    python -m pytest app/tests/newtest/test_agent_state.py -v
    
    echo -e "\n${YELLOW}2. Testando batch_api...${NC}"
    python -m pytest app/tests/newtest/test_batch_api.py -v
    
    echo -e "\n${YELLOW}3. Testando LLM queue...${NC}"
    python -m pytest app/tests/newtest/test_llm_queue.py -v
    
    echo -e "\n${YELLOW}4. Testando sharded cache...${NC}"
    python -m pytest app/tests/newtest/test_sharded_cache.py -v
    
    echo -e "\n${YELLOW}5. Testando tenant...${NC}"
    python -m pytest app/tests/newtest/test_tenant.py -v
}

# Função para executar todos os testes
run_all_tests() {
    echo -e "\n${YELLOW}=== Executando todos os testes ===${NC}"
    python -m pytest app/tests/newtest -v --tb=short
}

# Verificar argumentos da linha de comando
case "${1:-all}" in
    "specific")
        run_specific_tests
        ;;
    "all")
        run_all_tests
        ;;
    "state")
        echo -e "\n${YELLOW}=== Testando apenas agent_state ===${NC}"
        python -m pytest app/tests/newtest/test_agent_state.py -v -s
        ;;
    "batch")
        echo -e "\n${YELLOW}=== Testando apenas batch_api ===${NC}"
        python -m pytest app/tests/newtest/test_batch_api.py -v -s
        ;;
    "help")
        echo "Uso: $0 [all|specific|state|batch|help]"
        echo "  all      - Executa todos os testes (padrão)"
        echo "  specific - Executa apenas os testes que falharam"
        echo "  state    - Executa apenas test_agent_state.py"
        echo "  batch    - Executa apenas test_batch_api.py"
        echo "  help     - Mostra esta ajuda"
        exit 0
        ;;
    *)
        echo -e "${RED}Opção inválida: $1${NC}"
        echo "Use '$0 help' para ver as opções disponíveis"
        exit 1
        ;;
esac

# Código de saída
exit_code=$?

# Limpar variáveis de ambiente
unset PYTEST_CURRENT_TEST
unset SECRET_KEY
unset DB_NAME
unset REDIS_URL
unset DEBUG

if [ $exit_code -eq 0 ]; then
    echo -e "\n${GREEN}✓ Todos os testes executados com sucesso!${NC}"
else
    echo -e "\n${RED}✗ Alguns testes falharam. Verifique os logs acima.${NC}"
fi

echo -e "\n${YELLOW}=== Testes concluídos! ===${NC}"
exit $exit_code