import pandas as pd
import copy
import random
from collections import defaultdict
from math import floor
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

# =============================================================================
# Função auxiliar para cálculo da área (usa apenas os pares únicos)
# =============================================================================
def area_side(corridors):
    if not corridors:
        return 0
    # Obtém os pares (andar, corredor) sem duplicação
    unique_pairs = set((fl, corr) for fl, corr, _ in corridors)
    sorted_corr = sorted([pair[1] for pair in unique_pairs])
    if not sorted_corr:
        return 0
    actual_count = len(sorted_corr)
    ideal_count = (sorted_corr[-1] - sorted_corr[0]) // 2 + 1
    return actual_count if actual_count >= ideal_count else sorted_corr[-1] - sorted_corr[0]

# =============================================================================
# Função de custo: soma das áreas de todas as caixas
# =============================================================================
def cost_solution(solution):
    total_cost = 0
    for box in solution:
        total_cost += area_side(box["allocations"])
    return total_cost

# =============================================================================
# Funções de alocação de SKUs (método guloso)
# =============================================================================
def allocate_sku_old(sku, required, stock):
    entries = stock.get(sku, [])
    for i, (andar, corredor, qty) in enumerate(entries):
        if qty >= required:
            entries[i] = (andar, corredor, qty - required)
            return [(andar, corredor, required)]
    return None

def allocate_sku_new(sku, required, stock):
    allocated = []
    remaining = required
    entries = stock.get(sku, [])
    for i in range(len(entries)):
        andar, corredor, qty = entries[i]
        if remaining <= 0:
            break
        allocated_qty = min(qty, remaining)
        allocated.append((andar, corredor, allocated_qty))
        remaining -= allocated_qty
        entries[i] = (andar, corredor, qty - allocated_qty)
    if remaining > 0:
        raise Exception(f"Estoque insuficiente para {sku}: falta {remaining} peças")
    return allocated

def allocate_sku_greedy(sku, required, stock):
    allocation = allocate_sku_old(sku, required, stock)
    if allocation is not None:
        return allocation
    else:
        return allocate_sku_new(sku, required, stock)

# =============================================================================
# Pré-processamento: caixas e estoque
# =============================================================================
def load_data(caixas_path, estoque_path):
    caixas_df = pd.read_csv(caixas_path)
    estoque_df = pd.read_csv(estoque_path)
    return caixas_df, estoque_df

def preprocess_boxes(caixas_df):
    boxes = {}
    for _, row in caixas_df.iterrows():
        caixa_id = row["CAIXA_ID"]
        sku = row["SKU"]
        sku_full = f"SKU_{sku}" if not str(sku).startswith("SKU_") else str(sku)
        quantidade = row["PECAS"]
        classe = row["CLASSE_ONDA"]
        if caixa_id not in boxes:
            boxes[caixa_id] = {"caixa_id": caixa_id, "classe_onda": classe, "items": {}}
        boxes[caixa_id]["items"][sku_full] = boxes[caixa_id]["items"].get(sku_full, 0) + quantidade
    return list(boxes.values())

def preprocess_stock(estoque_df):
    stock = defaultdict(list)
    for _, row in estoque_df.iterrows():
        sku = row["SKU"]
        sku_full = f"SKU_{sku}" if not str(sku).startswith("SKU_") else str(sku)
        stock[sku_full].append((row["ANDAR"], row["CORREDOR"], row["PECAS"]))
    for sku in stock:
        stock[sku].sort(key=lambda x: -x[2])
    return stock

# =============================================================================
# Validação Global do Estoque
# =============================================================================
def validate_overall_stock(boxes, stock):
    required_totals = defaultdict(int)
    for box in boxes:
        for sku, qty in box["items"].items():
            required_totals[sku] += qty
    available_totals = defaultdict(int)
    for sku, entries in stock.items():
        for andar, corredor, qty in entries:
            available_totals[sku] += qty
    errors = []
    for sku, req in required_totals.items():
        avail = available_totals.get(sku, 0)
        if req > avail:
            errors.append(f"SKU {sku}: requerido {req}, disponível {avail}.")
    return errors

# =============================================================================
# Solução Inicial: alocação gulosa a nível de caixa
# =============================================================================
def allocate_boxes_greedy(boxes, stock):
    stock_alloc = copy.deepcopy(stock)
    solution = []
    for box in boxes:
        caixa_id = box["caixa_id"]
        classe = box["classe_onda"]
        for sku, required in box["items"].items():
            allocation = allocate_sku_greedy(sku, required, stock_alloc)
            solution.append({
                "caixa_id": caixa_id,
                "classe_onda": classe,
                "sku": sku,
                "required": required,
                "allocations": allocation
            })
    return solution, stock_alloc

# =============================================================================
# Função auxiliar para obter o estoque efetivo para um SKU para uma caixa específica
# =============================================================================
def get_effective_stock(sku, solution, box_index, original_stock):
    global_allocated = defaultdict(int)
    for i, box in enumerate(solution):
        if box["sku"] == sku:
            for (andar, corredor, qty) in box["allocations"]:
                global_allocated[(andar, corredor)] += qty
    global_available = defaultdict(int)
    for (andar, corredor, qty) in original_stock.get(sku, []):
        global_available[(andar, corredor)] += qty
    this_box_alloc = defaultdict(int)
    for (andar, corredor, qty) in solution[box_index]["allocations"]:
        this_box_alloc[(andar, corredor)] += qty
    effective = {}
    for key, avail in global_available.items():
        allocated_except = global_allocated.get(key, 0) - this_box_alloc.get(key, 0)
        effective[key] = avail - allocated_except
    effective_list = [(andar, corredor, qty) for ((andar, corredor), qty) in effective.items() if qty > 0]
    return effective_list

# =============================================================================
# Busca local (ILS) para refinar a solução, minimizando a área por caixa
# =============================================================================
def local_search_solution(solution, original_stock):
    improved = False
    for i in range(len(solution)):
        box = solution[i]
        current_cost = area_side(box["allocations"])
        sku = box["sku"]
        required = box["required"]
        effective_stock = get_effective_stock(sku, solution, i, original_stock)
        temp_stock = {sku: effective_stock}
        candidate = allocate_sku_old(sku, required, temp_stock)
        if candidate is not None:
            new_cost = area_side(candidate)
            if new_cost < current_cost and is_candidate_feasible_for_sku(solution, i, candidate, original_stock):
                box["allocations"] = candidate
                improved = True
    return solution, improved

def is_candidate_feasible_for_sku(solution, box_index, candidate_allocation, original_stock):
    sku = solution[box_index]["sku"]
    usage = defaultdict(int)
    for i, box in enumerate(solution):
        if box["sku"] == sku:
            if i == box_index:
                for alloc in candidate_allocation:
                    pos = (alloc[0], alloc[1])
                    usage[pos] += alloc[2]
            else:
                for alloc in box["allocations"]:
                    pos = (alloc[0], alloc[1])
                    usage[pos] += alloc[2]
    available = defaultdict(int)
    for pos in original_stock.get(sku, []):
        key = (pos[0], pos[1])
        available[key] += pos[2]
    for pos, used_qty in usage.items():
        if used_qty > available.get(pos, 0):
            return False
    return True

def ils_refine_solution(initial_solution, original_stock, max_iter=100, perturbation_strength=0.1):
    current_solution = copy.deepcopy(initial_solution)
    best_solution = copy.deepcopy(initial_solution)
    best_cost = cost_solution(best_solution)
    num_boxes = len(initial_solution)
    for i in range(max_iter):
        new_solution = copy.deepcopy(current_solution)
        num_perturb = max(1, int(perturbation_strength * num_boxes))
        indices = random.sample(range(num_boxes), num_perturb)
        for idx in indices:
            box = new_solution[idx]
            sku = box["sku"]
            required = box["required"]
            effective_stock = get_effective_stock(sku, new_solution, idx, original_stock)
            temp_stock = {sku: effective_stock}
            candidate = allocate_sku_old(sku, required, temp_stock)
            if candidate is not None and is_candidate_feasible_for_sku(new_solution, idx, candidate, original_stock):
                box["allocations"] = candidate
            else:
                candidate = allocate_sku_new(sku, required, temp_stock)
                if is_candidate_feasible_for_sku(new_solution, idx, candidate, original_stock):
                    box["allocations"] = candidate
        new_solution, _ = local_search_solution(new_solution, original_stock)
        new_cost = cost_solution(new_solution)
        if new_cost < best_cost:
            best_cost = new_cost
            best_solution = copy.deepcopy(new_solution)
        current_solution = new_solution
        print(f"Iteração {i+1}: custo = {new_cost}, melhor custo = {best_cost}")
    return best_solution

# =============================================================================
# Função para salvar a solução final a nível de caixa em CSV
# =============================================================================
def save_box_solution(solution, output_csv):
    rows = []
    for sol in solution:
        for alloc in sol["allocations"]:
            andar, corredor, qty = alloc
            rows.append({
                "caixa_id": sol["caixa_id"],
                "classe_onda": sol["classe_onda"],
                "sku": sol["sku"],
                "required": sol["required"],
                "andar": andar,
                "corridor": corredor,
                "allocated_qty": qty,
                "area": area_side(sol["allocations"])
            })
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"CSV de solução a nível de caixa salvo em: {output_csv}")

# =============================================================================
# Função para calcular estatísticas de área por caixa
# =============================================================================
def compute_box_area_statistics(solution):
    box_areas = {}
    for entry in solution:
        caixa_id = entry["caixa_id"]
        area_val = area_side(entry["allocations"])
        if caixa_id in box_areas:
            box_areas[caixa_id].append(area_val)
        else:
            box_areas[caixa_id] = [area_val]
    all_areas = [sum(areas)/len(areas) for areas in box_areas.values()]
    avg_area = sum(all_areas) / len(all_areas) if all_areas else 0
    min_area = min(all_areas) if all_areas else 0
    max_area = max(all_areas) if all_areas else 0
    return avg_area, min_area, max_area

# =============================================================================
# Função para validar a solução a nível de caixa e estoque
# =============================================================================
def validate_solution(initial_boxes, solution, initial_stock):
    errors = []
    allocated_by_box = {}
    for entry in solution:
        key = (entry["caixa_id"], entry["sku"])
        allocated_qty = sum(qty for _, _, qty in entry["allocations"])
        allocated_by_box[key] = allocated_by_box.get(key, 0) + allocated_qty
    for box in initial_boxes:
        caixa_id = box["caixa_id"]
        for sku, required in box["items"].items():
            key = (caixa_id, sku)
            if key not in allocated_by_box:
                errors.append(f"Caixa {caixa_id} - SKU {sku} não foi alocada.")
            else:
                allocated = allocated_by_box[key]
                if allocated != required:
                    errors.append(f"Caixa {caixa_id} - SKU {sku}: requerido {required} e alocado {allocated}.")
    stock_usage = defaultdict(lambda: defaultdict(int))
    for entry in solution:
        sku = entry["sku"]
        for andar, corredor, qty in entry["allocations"]:
            stock_usage[sku][(andar, corredor)] += qty
    for sku, positions in stock_usage.items():
        if sku not in initial_stock:
            errors.append(f"SKU {sku} alocado, mas não existe no estoque original.")
            continue
        available = defaultdict(int)
        for fl, corr, qty in initial_stock.get(sku, []):
            available[(fl, corr)] += qty
        for pos, used_qty in positions.items():
            if used_qty > available.get(pos, 0):
                errors.append(f"SKU {sku} na posição {pos}: alocado {used_qty}, disponível {available.get(pos, 0)}.")
    is_valid = (len(errors) == 0)
    return is_valid, errors

# =============================================================================
# Função para agregar as alocações por caixa (para agrupamento em ondas)
# =============================================================================
def aggregate_boxes(refined_solution):
    """
    Agrega as alocações de cada caixa agrupando os (ANDAR, CORREDOR) e somando as quantidades.
    """
    agg = {}
    for entry in refined_solution:
        cid = entry["caixa_id"]
        if cid not in agg:
            agg[cid] = {
                "caixa_id": cid,
                "classe_onda": entry["classe_onda"],
                "pieces": 0,
                "items": {},
                "corridors": defaultdict(int)
            }
        agg[cid]["pieces"] += entry["required"]
        for fl, corr, qty in entry["allocations"]:
            agg[cid]["corridors"][(fl, corr)] += qty
        sku = entry["sku"]
        if sku in agg[cid]["items"]:
            agg[cid]["items"][sku]["required"] += entry["required"]
            for fl, corr, qty in entry["allocations"]:
                agg[cid]["items"][sku]["allocations"][(fl, corr)] += qty
        else:
            item_alloc = defaultdict(int)
            for fl, corr, qty in entry["allocations"]:
                item_alloc[(fl, corr)] += qty
            agg[cid]["items"][sku] = {"required": entry["required"], "allocations": item_alloc}
    # Converter os dicionários para listas de tuplas
    for box in agg.values():
        box["corridors"] = [(fl, corr, qty) for (fl, corr), qty in box["corridors"].items()]
        for sku, data in box["items"].items():
            data["allocations"] = [(fl, corr, qty) for (fl, corr), qty in data["allocations"].items()]
    return list(agg.values())

# =============================================================================
# Classe Wave para agrupamento de caixas em ondas
# =============================================================================
class Wave:
    def __init__(self, wave_class):
        self.wave_class = wave_class
        self.boxes = []   # Cada caixa é um dict agregado
        self.total_pieces = 0
        self.corridors = []  # Concatenação de todas as alocações das caixas

    def add_box(self, box):
        self.boxes.append(box)
        self.total_pieces += box["pieces"]
        self.corridors.extend(box["corridors"])

    def area(self):
        return area_side(self.corridors)

# =============================================================================
# Novo GRASP para agrupar caixas em ondas
# =============================================================================
def grasp_group_boxes_into_waves(aggregated_boxes, iterations=50, alpha=0.3, wave_capacity=6000):
    best_solution = None
    best_cost = float('inf')
    for it in range(iterations):
        boxes_iter = copy.deepcopy(aggregated_boxes)
        random.shuffle(boxes_iter)
        waves = []
        for box in boxes_iter:
            feasible_waves = [w for w in waves if w.wave_class == box["classe_onda"] and (w.total_pieces + box["pieces"]) <= wave_capacity]
            if feasible_waves:
                candidate_costs = []
                for w in feasible_waves:
                    current_area = w.area()
                    new_area = area_side(w.corridors + box["corridors"])
                    incremental_cost = new_area - current_area
                    candidate_costs.append((incremental_cost, w))
                min_cost = min(cost for cost, _ in candidate_costs)
                max_cost = max(cost for cost, _ in candidate_costs)
                threshold = min_cost + alpha * (max_cost - min_cost)
                rcl = [w for cost, w in candidate_costs if cost <= threshold]
                chosen_wave = random.choice(rcl)
                chosen_wave.add_box(box)
            else:
                new_wave = Wave(box["classe_onda"])
                new_wave.add_box(box)
                waves.append(new_wave)
        total_area = sum(w.area() for w in waves)
        cost = total_area + len(waves) * 10
        if cost < best_cost:
            best_cost = cost
            best_solution = copy.deepcopy(waves)
    return best_solution

# =============================================================================
# Função para validar a solução final de ondas (cada caixa deve aparecer em uma única onda)
# =============================================================================
def validate_final_waves(aggregated_boxes, waves, wave_capacity):
    errors = []
    boxes_in_waves = defaultdict(int)
    for wave in waves:
        for box in wave.boxes:
            boxes_in_waves[box["caixa_id"]] += 1
    for box in aggregated_boxes:
        cid = box["caixa_id"]
        if boxes_in_waves.get(cid, 0) == 0:
            errors.append(f"Caixa {cid} não foi alocada em nenhuma onda.")
        elif boxes_in_waves.get(cid, 0) > 1:
            errors.append(f"Caixa {cid} foi alocada em múltiplas ondas ({boxes_in_waves.get(cid, 0)}).")
    return (len(errors) == 0), errors

# =============================================================================
# Função para salvar a solução final de ondas em CSV
# =============================================================================
def save_wave_solution(waves, output_csv):
    rows = []
    wave_counter = 1
    for wave in waves:
        wave_id = f"Onda_{wave_counter}"
        for box in wave.boxes:
            rows.append({
                "wave": wave_id,
                "classe_onda": wave.wave_class,
                "caixa_id": box["caixa_id"],
                "pieces": box["pieces"],
                "items": str(box["items"]),
                "corridors": str(box["corridors"])
            })
        wave_counter += 1
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"CSV final de ondas salvo em: {output_csv}")

# =============================================================================
# Função para paralelizar o agrupamento de caixas em ondas por classe
# =============================================================================
def process_wave_class(class_wave, aggregated_boxes, iterations, alpha, wave_capacity):
    boxes_class = [box for box in aggregated_boxes if box["classe_onda"] == class_wave]
    waves = grasp_group_boxes_into_waves(boxes_class, iterations=iterations, alpha=alpha, wave_capacity=wave_capacity)
    return class_wave, waves

def parallel_grasp_grouping(aggregated_boxes, iterations=50, alpha=0.3, wave_capacity=6000, max_workers=4):
    classes = list({box["classe_onda"] for box in aggregated_boxes})
    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_wave_class, cls, aggregated_boxes, iterations, alpha, wave_capacity): cls for cls in classes}
        for future in as_completed(futures):
            cls, waves = future.result()
            results[cls] = waves
    return results

# =============================================================================
# Função para salvar logs de validação em arquivo e resumir no terminal
# =============================================================================
def save_validation_log(filename, errors):
    with open(filename, "w", encoding="utf-8") as f:
        for err in errors:
            f.write(err + "\n")
    print(f"Detalhes dos erros salvos em: {filename}")

def summarize_errors(errors):
    summary = defaultdict(int)
    for err in errors:
        prefix = err.split(":")[0]
        summary[prefix] += 1
    for prefix, count in summary.items():
        print(f"{prefix}: {count} ocorrências")

# =============================================================================
# Execução completa com marcadores de tempo
# =============================================================================
if __name__ == "__main__":
    start_time = time.time()
    
    # Arquivos de entrada
    caixas_csv = "data/caixas.csv"      # Colunas: ONDA_ID, CAIXA_ID, PECAS, CLASSE_ONDA, SKU
    estoque_csv = "data/estoque.csv"    # Colunas: ANDAR, CORREDOR, SKU, PECAS
    
    # Carrega os dados
    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    
    # Pré-processa os dados
    boxes = preprocess_boxes(caixas_df)
    stock = preprocess_stock(estoque_df)
    
    print(f"Total de caixas agrupadas: {len(boxes)}")
    
    # Validação global do estoque
    stock_errors = validate_overall_stock(boxes, stock)
    if stock_errors:
        print("Erro: O estoque global não é suficiente para todas as caixas:")
        for err in stock_errors:
            print(" -", err)
        save_validation_log("stock_validation.log", stock_errors)
        exit(1)
    else:
        print("Validação inicial: Estoque global é suficiente para todas as caixas.")
    
    # Solução inicial: alocação gulosa a nível de caixa
    initial_solution, _ = allocate_boxes_greedy(boxes, stock)
    print(f"Solução inicial (gulosa) gerada para {len(initial_solution)} alocações.")
    
    # Refinamento da solução com ILS (parâmetros reduzidos para teste)
    refined_solution = ils_refine_solution(initial_solution, stock, max_iter=1, perturbation_strength=0.2)
    total_cost = cost_solution(refined_solution)
    print(f"Custo total (área) da solução refinada: {total_cost}")
    
    # Estatísticas de área por caixa
    avg_area, min_area, max_area = compute_box_area_statistics(refined_solution)
    print(f"Área média por caixa: {avg_area:.2f}")
    print(f"Área mínima entre as caixas: {min_area:.2f}")
    print(f"Área máxima entre as caixas: {max_area:.2f}")
    
    # Validação da solução a nível de caixa e estoque
    is_valid, validation_errors = validate_solution(boxes, refined_solution, stock)
    if is_valid:
        print("Solução validada com sucesso: todas as caixas e o estoque foram utilizados corretamente.")
    else:
        print("Erros na validação da solução (resumo):")
        summarize_errors(validation_errors)
        save_validation_log("solution_validation.log", validation_errors)
    
    # Agrega as alocações por caixa para obter caixas únicas
    aggregated_boxes = aggregate_boxes(refined_solution)
    print(f"Total de caixas únicas para agrupamento em ondas: {len(aggregated_boxes)}")
    
    # Agrupa as caixas em ondas usando GRASP em paralelo por classe
    wave_max_capacity = 
    print(f"Capacidade máxima por onda: {wave_max_capacity}")
    wave_solutions_by_class = parallel_grasp_grouping(aggregated_boxes, iterations=2, alpha=0.3, wave_capacity=wave_max_capacity, max_workers=4)
    final_waves = []
    for cls in wave_solutions_by_class:
        final_waves.extend(wave_solutions_by_class[cls])
    total_wave_area = sum(w.area() for w in final_waves)
    avg_wave_area = total_wave_area / len(final_waves) if final_waves else 0
    print(f"Total de ondas: {len(final_waves)}")
    print(f"Área média por onda: {avg_wave_area:.2f}")
    
    # Validação final das ondas: cada caixa deve estar em uma única onda
    valid_waves, wave_errors = validate_final_waves(aggregated_boxes, final_waves, 6000)
    if valid_waves:
        print("Validação final das ondas: OK!")
    else:
        print("Erros na validação final das ondas (resumo):")
        summarize_errors(wave_errors)
        save_validation_log("waves_validation.log", wave_errors)
    
    # Salva o CSV final de ondas
    output_csv = "solucao_ondas_final.csv"
    save_wave_solution(final_waves, output_csv)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Tempo total de execução: {elapsed_time:.2f} segundos")
