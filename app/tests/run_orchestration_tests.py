# app/tests/run_orchestration_tests.py
import unittest
import os
import sys

# Adicionar em app/tests/run_orchestration_tests.py após as importações

def run_tests_with_result():
    """Executa todos os testes e retorna o resultado."""
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('app/tests/test_orchestration', pattern='test_*.py')
    
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    return result

def run_specific_test(test_module_name):
    """Executa um módulo de teste específico."""
    print(f"\nExecutando teste específico: {test_module_name}\n")
    
    try:
        module = __import__(f"app.tests.test_orchestration.{test_module_name}")
        module_tests = getattr(module.tests.test_orchestration, test_module_name)
        
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(module_tests)
        
        test_runner = unittest.TextTestRunner(verbosity=2)
        return test_runner.run(test_suite)
    except (ImportError, AttributeError) as e:
        print(f"Erro ao importar módulo de teste: {str(e)}")
        return None

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Descobrir e executar todos os testes
def run_tests():
    """Executa todos os testes de orquestração."""
    print("=" * 80)
    print(" TESTES DA ORQUESTRAÇÃO DE AGENTES COM LANGGRAPH ".center(80, "="))
    print("=" * 80 + "\n")
    
    # Descobrir testes - apenas em test_orchestration
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('app/tests/test_orchestration', pattern='test_*.py')
    
    # Executar testes
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    print("\n" + "=" * 80)
    print(f" RESULTADO: {result.testsRun} testes executados, {len(result.errors)} erros, {len(result.failures)} falhas ".center(80, "="))
    print("=" * 80)
    
    return result

if __name__ == "__main__":
    run_tests()