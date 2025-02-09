import csv
import sys
from experiments.experiments_runner import (
    run_experiment_default,
    run_experiment_fixed_limit,
    run_experiment_proportional,
    run_experiment_by_config
)

def parse_config_string(config_str: str):
    """
    Converte uma string de configuração no formato:
      "(min_count, max_count, caixas_por_onda);(min_count, max_count, caixas_por_onda);..."
    Exemplo:
      "(0,10,2);(11,100,10);(101,500,25);(501,10000,50);(10001,inf,50)"
    para uma lista de tuplas.
    """
    config_list = []
    for part in config_str.split(";"):
        part = part.strip().strip("()")
        if not part:
            continue
        items = part.split(",")
        if len(items) != 3:
            continue
        try:
            min_count = int(items[0].strip())
            max_count = items[1].strip().lower()
            if max_count in ['inf', 'infty', 'infinite']:
                max_count = float('inf')
            else:
                max_count = int(max_count)
            caixas_por_onda = int(items[2].strip())
            config_list.append((min_count, max_count, caixas_por_onda))
        except ValueError:
            continue
    return config_list

def get_input(prompt, default=None, cast_func=None):
    """
    Exibe um prompt e retorna o valor inserido. Se vazio e existir um default, retorna default.
    Se cast_func for fornecido, tenta converter o valor.
    """
    valor = input(prompt).strip()
    if not valor and default is not None:
        return default
    if cast_func is not None:
        try:
            return cast_func(valor)
        except Exception:
            print("Valor inválido. Usando o valor padrão.")
            return default
    return valor

def main():
    print("========================================")
    print("   Bem-vindo aos Experimentos GRASP     ")
    print("========================================\n")
    
    while True:
        print("Selecione o tipo de experimento:")
        print("0. Default (sem limites de onda)")
        print("1. Fixed Limit (limite fixo por classe)")
        print("2. Proportional (limite total proporcional)")
        print("3. Config (limite automático via configuração)")
        print("4. Test (varia tamanhos de onda)")
        print("5. Sair")
        
        opcao = input("Digite o número da opção desejada: ").strip()
        
        if opcao == "0":
            # Default
            caixas_csv = get_input("Informe o caminho para o arquivo de caixas (default: data/caixas.csv): ", "data/caixas.csv")
            estoque_csv = get_input("Informe o caminho para o arquivo de estoque (default: data/estoque.csv): ", "data/estoque.csv")
            iterations = get_input("Informe o número de iterações (default: 10): ", 10, int)
            alpha = get_input("Informe o valor de alpha (default: 0.3): ", 0.3, float)
            debug_input = get_input("Habilitar debug? (s/n, default: n): ", "n").lower()
            debug = True if debug_input == "s" else False
            
            print("\nExecutando experimento DEFAULT (sem limites de onda)...\n")
            run_experiment_default(
                caixas_csv=caixas_csv,
                estoque_csv=estoque_csv,
                iterations=iterations,
                alpha=alpha,
                debug=debug
            )
        
        elif opcao == "1":
            # Fixed Limit
            caixas_csv = get_input("Informe o caminho para o arquivo de caixas (default: data/caixas.csv): ", "data/caixas.csv")
            estoque_csv = get_input("Informe o caminho para o arquivo de estoque (default: data/estoque.csv): ", "data/estoque.csv")
            max_waves = get_input("Informe o valor de max_waves (limite fixo por classe): ", cast_func=int)
            if max_waves is None:
                print("Valor de max_waves é obrigatório. Tente novamente.\n")
                continue
            iterations = get_input("Informe o número de iterações (default: 10): ", 10, int)
            alpha = get_input("Informe o valor de alpha (default: 0.3): ", 0.3, float)
            debug_input = get_input("Habilitar debug? (s/n, default: n): ", "n").lower()
            debug = True if debug_input == "s" else False
            
            print(f"\nExecutando experimento FIXED com max_waves = {max_waves}...\n")
            run_experiment_fixed_limit(
                caixas_csv=caixas_csv,
                estoque_csv=estoque_csv,
                max_waves=max_waves,
                iterations=iterations,
                alpha=alpha,
                debug=debug
            )
        
        elif opcao == "2":
            # Proportional
            caixas_csv = get_input("Informe o caminho para o arquivo de caixas (default: data/caixas.csv): ", "data/caixas.csv")
            estoque_csv = get_input("Informe o caminho para o arquivo de estoque (default: data/estoque.csv): ", "data/estoque.csv")
            total_max_waves = get_input("Informe o valor de total_max_waves (limite total proporcional): ", cast_func=int)
            if total_max_waves is None:
                print("Valor de total_max_waves é obrigatório. Tente novamente.\n")
                continue
            iterations = get_input("Informe o número de iterações (default: 10): ", 10, int)
            alpha = get_input("Informe o valor de alpha (default: 0.3): ", 0.3, float)
            debug_input = get_input("Habilitar debug? (s/n, default: n): ", "n").lower()
            debug = True if debug_input == "s" else False
            
            print(f"\nExecutando experimento PROPORTIONAL com total_max_waves = {total_max_waves}...\n")
            run_experiment_proportional(
                caixas_csv=caixas_csv,
                estoque_csv=estoque_csv,
                total_max_waves=total_max_waves,
                iterations=iterations,
                alpha=alpha,
                debug=debug
            )
        
        elif opcao == "3":
            # Config
            caixas_csv = get_input("Informe o caminho para o arquivo de caixas (default: data/caixas.csv): ", "data/caixas.csv")
            estoque_csv = get_input("Informe o caminho para o arquivo de estoque (default: data/estoque.csv): ", "data/estoque.csv")
            config_str = get_input("Informe a configuração (Ex: (0,10,2);(11,100,10);(101,500,25);(501,10000,50);(10001,inf,50)): ")
            config_list = parse_config_string(config_str)
            if not config_list:
                print("A string de configuração não pôde ser interpretada corretamente.\n")
                continue
            iterations = get_input("Informe o número de iterações (default: 10): ", 10, int)
            alpha = get_input("Informe o valor de alpha (default: 0.3): ", 0.3, float)
            debug_input = get_input("Habilitar debug? (s/n, default: n): ", "n").lower()
            debug = True if debug_input == "s" else False
            
            print("\nExecutando experimento CONFIG com a seguinte configuração:")
            for cfg in config_list:
                print("  -", cfg)
            print("")
            run_experiment_by_config(
                caixas_csv=caixas_csv,
                estoque_csv=estoque_csv,
                config=config_list,
                iterations=iterations,
                alpha=alpha,
                debug=debug
            )
        
        elif opcao == "4":
            # Test
            caixas_csv = get_input("Informe o caminho para o arquivo de caixas (default: data/caixas.csv): ", "data/caixas.csv")
            estoque_csv = get_input("Informe o caminho para o arquivo de estoque (default: data/estoque.csv): ", "data/estoque.csv")
            test_wave_sizes_str = get_input("Informe os tamanhos de onda para teste (ex: 50,100,150): ")
            try:
                wave_sizes = [int(x.strip()) for x in test_wave_sizes_str.split(",")]
            except ValueError:
                print("Os tamanhos de onda devem ser números inteiros separados por vírgula.\n")
                continue
            iterations = get_input("Informe o número de iterações (default: 10): ", 10, int)
            alpha = get_input("Informe o valor de alpha (default: 0.3): ", 0.3, float)
            debug_input = get_input("Habilitar debug? (s/n, default: n): ", "n").lower()
            debug = True if debug_input == "s" else False
            results = []

            for size in wave_sizes:
                print(f"\n=== Executando teste para tamanho de onda fixo: {size} ===\n")
                metrics = run_experiment_fixed_limit(
                    caixas_csv=caixas_csv,
                    estoque_csv=estoque_csv,
                    max_waves=size,
                    iterations=iterations,
                    alpha=alpha,
                    debug=debug
                )
                results.append({
                    "wave_size": size,
                    "total_waves": metrics["total_waves"],
                    "avg_area": metrics["avg_area"]
                })

            # Salva os resultados do modo teste em um CSV
            with open("results/test_mode_results.csv", "w", newline="") as csvfile:
                fieldnames = ["wave_size", "total_waves", "avg_area"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in results:
                    writer.writerow(row)
            print("Resultados de teste salvos em test_mode_results.csv")
                    
        elif opcao == "5":
            print("Encerrando o programa.")
            sys.exit(0)
        
        else:
            print("Opção inválida. Tente novamente.\n")
        
        print("\n----------------------------------------\n")

if __name__ == "__main__":
    main()
