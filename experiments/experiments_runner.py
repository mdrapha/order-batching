# experiments/experiments_runner.py

import copy
from math import floor, ceil
from collections import defaultdict

# Importa funções utilitárias do projeto
from utils.iotools import load_data, preprocess_data, save_box_wave_table, save_stock_usage_table
from grasp.validation import validate_solution
from grasp.allocation import allocate_sku_combined
from grasp.grasp_solver import GraspSolver  # Classe que encapsula o algoritmo GRASP

def run_experiment_default(caixas_csv: str, estoque_csv: str,
                           iterations: int = 10, alpha: float = 0.3, debug: bool = False):
    """
    Executa o experimento sem limitar o número de ondas (modo padrão).
    Nesse modo, o algoritmo gera ondas conforme necessário, sem impor um limite.
    Ao final, imprime os resultados, salva os arquivos CSV e retorna um dicionário com:
      - total de ondas geradas
      - área média final
    """
    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    boxes, stock = preprocess_data(caixas_df, estoque_df)
    original_stock = copy.deepcopy(stock)
    
    solution_all = []
    logs_all = []
    wave_classes = set(box["wave_class"] for box in boxes)
    
    for wave_class in wave_classes:
        boxes_class = [box for box in boxes if box["wave_class"] == wave_class]
        # Aloca as posições para cada caixa
        for box in boxes_class:
            box["corridors"] = allocate_sku_combined(box["sku"], box["pieces"], stock)
        # Cria o solver sem limite de ondas (max_waves = None)
        solver = GraspSolver(iterations=iterations, alpha=alpha, max_waves=None, debug=debug)
        solution, logs = solver.solve(boxes_class, stock)
        solution_all.extend(solution)
        logs_all.extend(logs)
    
    valid, errors = validate_solution(solution_all, boxes, original_stock)
    if valid:
        print("✅ Solução validada com sucesso (Default - sem limite de ondas).")
    else:
        print("❌ Erros na validação (Default - sem limite de ondas):", errors)
    
    # Calcula os resultados finais: área total, quantidade de ondas e área média
    total_area = sum(w.area() for w in solution_all)
    n_waves = len(solution_all)
    avg_area = total_area / n_waves if n_waves > 0 else 0.0
    print(f"Total de ondas geradas: {n_waves}")
    print(f"Área média final: {avg_area:.2f}")
    
    save_box_wave_table(solution_all, "resultado_solucao_default.csv")
    save_stock_usage_table(solution_all, original_stock, "stock_usage_table_default.csv")
    print("Resultados salvos: resultado_solucao_default.csv e stock_usage_table_default.csv")
    
    return {"total_waves": n_waves, "avg_area": avg_area}


def run_experiment_fixed_limit(caixas_csv: str, estoque_csv: str, max_waves: int,
                               iterations: int = 10, alpha: float = 0.3, debug: bool = False):
    """
    Executa o experimento usando um limite fixo de ondas para todas as classes.
    Ao final, imprime os resultados, salva os arquivos CSV e retorna um dicionário com:
      - total de ondas geradas
      - área média final
    """
    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    boxes, stock = preprocess_data(caixas_df, estoque_df)
    original_stock = copy.deepcopy(stock)
    
    solution_all = []
    logs_all = []
    wave_classes = set(box["wave_class"] for box in boxes)
    
    for wave_class in wave_classes:
        boxes_class = [box for box in boxes if box["wave_class"] == wave_class]
        for box in boxes_class:
            box["corridors"] = allocate_sku_combined(box["sku"], box["pieces"], stock)
        solver = GraspSolver(iterations=iterations, alpha=alpha, max_waves=max_waves, debug=debug)
        solution, logs = solver.solve(boxes_class, stock)
        solution_all.extend(solution)
        logs_all.extend(logs)
    
    valid, errors = validate_solution(solution_all, boxes, original_stock)
    if valid:
        print("✅ Solução validada com sucesso (Fixed Limit).")
    else:
        print("❌ Erros na validação (Fixed Limit):", errors)
    
    total_area = sum(w.area() for w in solution_all)
    n_waves = len(solution_all)
    avg_area = total_area / n_waves if n_waves > 0 else 0.0
    print(f"Total de ondas geradas: {n_waves}")
    print(f"Área média final: {avg_area:.2f}")
    
    save_box_wave_table(solution_all, "resultado_solucao_fixed.csv")
    save_stock_usage_table(solution_all, original_stock, "stock_usage_table_fixed.csv")
    print("Resultados salvos: resultado_solucao_fixed.csv e stock_usage_table_fixed.csv")
    
    return {"total_waves": n_waves, "avg_area": avg_area}
    

def distribute_waves_among_classes(boxes, total_max_waves):
    """
    Distribui um limite total de ondas proporcionalmente ao número de caixas de cada classe.
    
    Retorna um dicionário { wave_class: max_waves_para_essa_classe }.
    """
    wave_counts = defaultdict(int)
    for box in boxes:
        wave_counts[box["wave_class"]] += 1
    classes_list = list(wave_counts.keys())
    sum_boxes = sum(wave_counts[c] for c in classes_list)
    
    if total_max_waves < len(classes_list):
        total_max_waves = len(classes_list)
    
    waves_distribution = {}
    fractional_parts = []
    for c in classes_list:
        proportion = wave_counts[c] / sum_boxes if sum_boxes > 0 else 1.0
        raw = proportion * total_max_waves
        base = int(floor(raw))
        if base < 1:
            base = 1
        waves_distribution[c] = base
        fractional_parts.append((c, raw - base))
    
    current_sum = sum(waves_distribution.values())
    if current_sum < total_max_waves:
        leftover = total_max_waves - current_sum
        fractional_parts.sort(key=lambda x: x[1], reverse=True)
        idx = 0
        while leftover > 0:
            c, _ = fractional_parts[idx]
            waves_distribution[c] += 1
            leftover -= 1
            idx = (idx + 1) % len(fractional_parts)
    elif current_sum > total_max_waves:
        excess = current_sum - total_max_waves
        fractional_parts.sort(key=lambda x: x[1])
        idx = 0
        while excess > 0 and idx < len(fractional_parts):
            c, _ = fractional_parts[idx]
            if waves_distribution[c] > 1:
                waves_distribution[c] -= 1
                excess -= 1
            else:
                idx += 1
    return waves_distribution


def run_experiment_proportional(caixas_csv: str, estoque_csv: str, total_max_waves: int,
                                iterations: int = 10, alpha: float = 0.3, debug: bool = False):
    """
    Executa o experimento onde um limite total de ondas é definido e distribuído proporcionalmente entre as classes.
    Ao final, imprime os resultados, salva os arquivos CSV e retorna um dicionário com:
      - total de ondas geradas
      - área média final
    """
    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    boxes, stock = preprocess_data(caixas_df, estoque_df)
    original_stock = copy.deepcopy(stock)
    
    wave_limits = distribute_waves_among_classes(boxes, total_max_waves)
    print("Distribuição de ondas por classe:")
    for wave_class, limit in wave_limits.items():
        print(f"  - {wave_class}: {limit} ondas (máx.)")
    
    solution_all = []
    logs_all = []
    wave_classes = set(box["wave_class"] for box in boxes)
    
    for wave_class in wave_classes:
        boxes_class = [box for box in boxes if box["wave_class"] == wave_class]
        for box in boxes_class:
            box["corridors"] = allocate_sku_combined(box["sku"], box["pieces"], stock)
        solver = GraspSolver(iterations=iterations, alpha=alpha, max_waves=wave_limits[wave_class], debug=debug)
        solution, logs = solver.solve(boxes_class, stock)
        solution_all.extend(solution)
        logs_all.extend(logs)
    
    valid, errors = validate_solution(solution_all, boxes, original_stock)
    if valid:
        print("✅ Solução validada com sucesso (Proportional).")
    else:
        print("❌ Erros na validação (Proportional):", errors)
    
    total_area = sum(w.area() for w in solution_all)
    n_waves = len(solution_all)
    avg_area = total_area / n_waves if n_waves > 0 else 0.0
    print(f"Total de ondas geradas: {n_waves}")
    print(f"Área média final: {avg_area:.2f}")
    
    save_box_wave_table(solution_all, "resultado_solucao_proportional.csv")
    save_stock_usage_table(solution_all, original_stock, "stock_usage_table_proportional.csv")
    print("Resultados salvos: resultado_solucao_proportional.csv e stock_usage_table_proportional.csv")
    
    return {"total_waves": n_waves, "avg_area": avg_area}


def calculate_max_waves_by_class(boxes, config):
    """
    Calcula o número máximo de ondas para cada classe com base em uma configuração.
    
    'config' é uma lista de tuplas: (min_count, max_count, caixas_por_onda).
    Retorna um dicionário { wave_class: max_waves }.
    """
    counts = defaultdict(int)
    for box in boxes:
        counts[box["wave_class"]] += 1
    max_waves_by_class = {}
    for wave_class, total_count in counts.items():
        ratio = None
        for min_count, max_count, caixas_por_onda in config:
            if total_count >= min_count and total_count <= max_count:
                ratio = caixas_por_onda
                break
        if ratio is None:
            ratio = config[-1][2]
        max_waves_by_class[wave_class] = ceil(total_count / ratio)
    return max_waves_by_class


def run_experiment_by_config(caixas_csv: str, estoque_csv: str, config, iterations: int = 10,
                             alpha: float = 0.3, debug: bool = False):
    """
    Executa o experimento onde o limite máximo de ondas para cada classe é definido automaticamente,
    com base em uma configuração (lista de tuplas: (min_count, max_count, caixas_por_onda)).
    Ao final, imprime os resultados, salva os arquivos CSV e retorna um dicionário com:
      - total de ondas geradas
      - área média final
    """
    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    boxes, stock = preprocess_data(caixas_df, estoque_df)
    original_stock = copy.deepcopy(stock)
    
    max_waves_by_class = calculate_max_waves_by_class(boxes, config)
    print("Limite máximo de ondas por classe (calculado pela configuração):")
    for wave_class, max_waves in max_waves_by_class.items():
        count = sum(1 for box in boxes if box["wave_class"] == wave_class)
        print(f"  - {wave_class}: {max_waves} (baseado em {count} caixas)")
    
    solution_all = []
    logs_all = []
    wave_classes = set(box["wave_class"] for box in boxes)
    
    for wave_class in wave_classes:
        boxes_class = [box for box in boxes if box["wave_class"] == wave_class]
        for box in boxes_class:
            box["corridors"] = allocate_sku_combined(box["sku"], box["pieces"], stock)
        solver = GraspSolver(iterations=iterations, alpha=alpha,
                              max_waves=max_waves_by_class[wave_class], debug=debug)
        solution, logs = solver.solve(boxes_class, stock)
        solution_all.extend(solution)
        logs_all.extend(logs)
    
    valid, errors = validate_solution(solution_all, boxes, original_stock)
    if valid:
        print("✅ Solução validada com sucesso (Config).")
    else:
        print("❌ Erros na validação (Config):", errors)
    
    total_area = sum(w.area() for w in solution_all)
    n_waves = len(solution_all)
    avg_area = total_area / n_waves if n_waves > 0 else 0.0
    print(f"Total de ondas geradas: {n_waves}")
    print(f"Área média final: {avg_area:.2f}")
    
    save_box_wave_table(solution_all, "results/resultado_solucao_config.csv")
    save_stock_usage_table(solution_all, original_stock, "logs/stock_usage_table_config.csv")
    print("Resultados salvos: resultado_solucao_config.csv e stock_usage_table_config.csv")
    
    return {"total_waves": n_waves, "avg_area": avg_area}
