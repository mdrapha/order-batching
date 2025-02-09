import pandas as pd
import time
import random
from collections import defaultdict
from tqdm import tqdm
import copy
from concurrent.futures import ProcessPoolExecutor, as_completed
import re
from math import floor, ceil

# =============================================================================
# Função global para o defaultdict de floors (evita lambda não pickleable)
# =============================================================================
def default_floor():
    return {'par': defaultdict(int), 'impar': defaultdict(int)}

# =============================================================================
# Logger simples
# =============================================================================
class DebugLogger:
    def __init__(self, max_lines=5, enable=False):
        self.max_lines = max_lines
        self.enable = enable
    def log(self, message):
        if self.enable:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")

# =============================================================================
# Funções de carregamento e pré-processamento
# =============================================================================
def load_data(caixas_path, estoque_path):
    caixas_df = pd.read_csv(caixas_path)
    estoque_df = pd.read_csv(estoque_path)
    return caixas_df, estoque_df

def preprocess_data(caixas_df, estoque_df):
    boxes = []
    for _, row in caixas_df.iterrows():
        box = {
            'wave_class': row['CLASSE_ONDA'],
            'caixa_id': row['CAIXA_ID'],
            'pieces': row['PECAS'],
            'sku': row['SKU']
        }
        boxes.append(box)
    stock = defaultdict(list)
    for _, row in estoque_df.iterrows():
        stock[row['SKU']].append((row['ANDAR'], row['CORREDOR'], row['PECAS']))
    for sku in stock:
        stock[sku].sort(key=lambda x: -x[2])
    return boxes, stock

# =============================================================================
# Versões de allocate_sku
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
        raise ValueError(f"Estoque insuficiente para SKU {sku}")
    return allocated

def allocate_sku_combined(sku, required, stock):
    """
    Tenta primeiro a alocação "old" (tudo de uma mesma posição).
    Se não conseguir, faz a alocação "new" (fracionado).
    """
    result = allocate_sku_old(sku, required, stock)
    if result is not None:
        return result
    else:
        result = allocate_sku_new(sku, required, stock)
        return result

# =============================================================================
# Função auxiliar para cálculo da área (usa apenas os pares únicos)
# =============================================================================
def area_side(corridors):
    if not corridors:
        return 0
    unique_pairs = set((floor, corridor) for floor, corridor, _ in corridors)
    sorted_corr = sorted(pair[1] for pair in unique_pairs)
    if not sorted_corr:
        return 0
    actual_count = len(sorted_corr)
    ideal_count = (sorted_corr[-1] - sorted_corr[0]) // 2 + 1
    return actual_count if actual_count >= ideal_count else sorted_corr[-1] - sorted_corr[0]

# =============================================================================
# Classe Wave
# =============================================================================
class Wave:
    def __init__(self, wave_class, debug_enabled=False):
        self.debug_logger = DebugLogger(enable=debug_enabled)
        self.wave_class = wave_class
        self.boxes = []  # Cada caixa é montada em apenas uma onda.
        self.total_pieces = 0
        self.floors = defaultdict(default_floor)

    def add_box(self, box, simulate=False):
        self.debug_logger.log(f"Adicionando caixa {box['caixa_id']} à onda {self.wave_class} (simulate={simulate})")
        self.boxes.append(box)
        self.total_pieces += box['pieces']
        for floor, corridor, alloc_qty in box['corridors']:
            side = 'par' if corridor % 2 == 0 else 'impar'
            self.floors[floor][side][corridor] += alloc_qty
        if not simulate:
            box["assigned_wave"] = self

    def remove_box(self, box, simulate=False):
        self.debug_logger.log(f"Removendo caixa {box['caixa_id']} da onda {self.wave_class} (simulate={simulate})")
        if box in self.boxes:
            self.boxes.remove(box)
            self.total_pieces -= box['pieces']
            for floor, corridor, alloc_qty in box['corridors']:
                side = 'par' if corridor % 2 == 0 else 'impar'
                self.floors[floor][side][corridor] -= alloc_qty
                if self.floors[floor][side][corridor] <= 0:
                    del self.floors[floor][side][corridor]
            # Remove o andar se não houver mais par/impar
            floors_to_remove = []
            for f, sides in self.floors.items():
                if not sides['par'] and not sides['impar']:
                    floors_to_remove.append(f)
            for f in floors_to_remove:
                del self.floors[f]

            if not simulate:
                box["assigned_wave"] = None
        else:
            self.debug_logger.log(f"Caixa {box['caixa_id']} não encontrada na onda {self.wave_class}")

    @property
    def corridors(self):
        result = set()
        for floor, sides in self.floors.items():
            for side in ['par', 'impar']:
                for corridor in sides[side]:
                    result.add((floor, corridor))
        return result

    def area(self):
        if self.total_pieces <= 0:
            return 0
        total_area = 0
        for floor, sides in self.floors.items():
            floor_area = 0
            for side in ['par', 'impar']:
                corridors = [(floor, corridor, qty) for corridor, qty in sides[side].items()]
                floor_area += area_side(corridors)
            total_area += floor_area
        num_floors = len(self.floors)
        if num_floors > 0:
            floor_list = sorted(self.floors.keys())
            base_penalty = 10 * (num_floors - 1)
            extra_penalty = 5 * (floor_list[-1] - floor_list[0])
        else:
            base_penalty = extra_penalty = 0
        return total_area + base_penalty + extra_penalty

# =============================================================================
# Função GRASP com métrica ponderada (área e quantidade de ondas)
# =============================================================================
def grasp_order_batching(
    boxes,
    stock,
    iterations=1,
    alpha=0.3,
    max_local_iterations=10, 
    debug_enabled=False,
    w_area=1.0,
    w_waves=0.1,
    max_waves=None  # <--- se não for None, limita o nº de ondas criadas
):
    """
    GRASP que cria ondas para um conjunto de caixas (todas de uma mesma wave_class).
    Se max_waves não for None, limita o número de ondas criadas.
    """
    global_logger = DebugLogger(enable=debug_enabled)
    global_logger.log("Iniciando processo GRASP")
    best_solution = None
    best_avg_area = float('inf')

    # Ordena as caixas; você pode ajustar o critério conforme necessário
    sorted_boxes = sorted(boxes, key=lambda x: -len(x.get('corridors', [])))
    iteration_logs = []

    for it in tqdm(range(iterations), desc="Processando GRASP", unit="iter", leave=False):
        # "Reseta" a solução, garantindo que nenhuma caixa esteja alocada
        for box in sorted_boxes:
            box["assigned_wave"] = None

        waves = []

        for box in sorted_boxes:
            if box.get("assigned_wave") is not None:
                continue  # Já foi alocado em alguma onda

            current_waves_count = len(waves)

            # Ondas factíveis = mesma classe e ainda com espaço < 6000 peças
            feasible_waves = [
                w for w in waves
                if w.wave_class == box['wave_class']
                and w.total_pieces + box['pieces'] <= 6000
            ]
            candidates = []

            # 1) Tentar colocar em cada onda existente (viável)
            for wave in feasible_waves:
                original_area = wave.area()
                wave.add_box(box, simulate=True)
                new_area = wave.area()
                wave.remove_box(box, simulate=True)
                metric = w_area * new_area + w_waves * current_waves_count
                candidates.append((metric, wave, False))  # False = "onda existente"

            # 2) Tentar criar uma nova onda, se não ultrapassar max_waves
            can_create_new = True
            if (max_waves is not None) and (current_waves_count >= max_waves):
                can_create_new = False

            if can_create_new:
                new_wave = Wave(box['wave_class'], debug_enabled=debug_enabled)
                new_wave.add_box(box, simulate=False)
                metric_new = w_area * new_wave.area() + w_waves * (current_waves_count + 1)
                candidates.append((metric_new, new_wave, True))  # True = "nova onda"

            if not candidates:
                # não foi possível alocar esta caixa em nenhuma onda
                continue

            # Escolha GRASP
            min_val = min(cand[0] for cand in candidates)
            max_val = max(cand[0] for cand in candidates)
            threshold = min_val + alpha * (max_val - min_val)
            rcl = [cand for cand in candidates if cand[0] <= threshold]
            chosen_metric, selected_wave, is_new = random.choice(rcl)

            if is_new:
                waves.append(selected_wave)
            else:
                selected_wave.add_box(box, simulate=False)

        total_area = sum(w.area() for w in waves)
        avg_area = total_area / len(waves) if waves else float('inf')

        if avg_area < best_avg_area:
            best_avg_area = avg_area
            # Clonar a melhor solução
            best_solution = [w for w in waves]

        iteration_log = {
            "wave_class": sorted_boxes[0]['wave_class'] if sorted_boxes else None,
            "iteration": it + 1,
            "best_avg_area": best_avg_area,
            "n_waves": len(waves),
            "n_boxes": len(sorted_boxes)
        }
        iteration_logs.append(iteration_log)

    return best_solution, iteration_logs

# =============================================================================
# Funções de validação e salvamento
# =============================================================================
def validate_solution_by_location(solution, original_stock, verbose=False):
    used_by_location = defaultdict(int)
    for wave in solution:
        for box in wave.boxes:
            sku = box["sku"]
            for floor, corridor, alloc_qty in box.get("corridors", []):
                used_by_location[(sku, floor, corridor)] += alloc_qty

    errors = []
    for key, used in used_by_location.items():
        sku, floor, corridor = key
        available = sum(qty for f, c, qty in original_stock.get(sku, []) if f == floor and c == corridor)
        if verbose:
            print(f"[DEBUG] SKU {sku}, floor {floor}, corridor {corridor}: used={used}, available={available}")
        if used > available:
            deficit = used - available
            errors.append(
                f"Para SKU {sku} no piso {floor} e corredor {corridor}, "
                f"foram utilizadas {used} peças, mas o estoque disponível é {available}. "
                f"Falta {deficit} peças."
            )
    return errors

def validate_solution(solution, all_boxes, original_stock):
    """
    Verifica se as ondas do solution são válidas em relação ao estoque e aos totais de peças.
    """
    errors = []
    for wave in solution:
        soma_pieces = sum(box["pieces"] for box in wave.boxes)
        if soma_pieces != wave.total_pieces:
            errors.append(
                f"Onda {wave.wave_class}: soma das peças ({soma_pieces}) "
                f"difere do total ({wave.total_pieces})."
            )

    sku_usage = defaultdict(int)
    for wave in solution:
        for box in wave.boxes:
            sku_usage[box["sku"]] += box["pieces"]

    for sku, total_used in sku_usage.items():
        total_available = sum(qty for _, _, qty in original_stock.get(sku, []))
        if total_used > total_available:
            errors.append(
                f"SKU {sku}: utilizado {total_used} peças, mas estoque disponível é {total_available}."
            )

    # Remove ondas vazias (se houver)
    solution[:] = [wave for wave in solution if wave.boxes]

    valid = (len(errors) == 0)
    return valid, errors

def save_box_wave_table(solution, filename):
    rows = []
    for idx, wave in enumerate(solution, start=1):
        wave_id = f"Onda_{idx}"
        for box in wave.boxes:
            unique_allocations = list({(floor, corridor, alloc_qty) for floor, corridor, alloc_qty in box.get("corridors", [])})
            if unique_allocations:
                for floor, corridor, alloc_qty in unique_allocations:
                    row = {
                        "wave": wave_id,
                        "wave_class": wave.wave_class,
                        "caixa_id": box["caixa_id"],
                        "sku": box["sku"],
                        "pieces": box["pieces"],
                        "floor": floor,
                        "corridor": corridor,
                        "allocated_qty": alloc_qty
                    }
                    rows.append(row)
            else:
                row = {
                    "wave": wave_id,
                    "wave_class": wave.wave_class,
                    "caixa_id": box["caixa_id"],
                    "sku": box["sku"],
                    "pieces": box["pieces"],
                    "floor": "",
                    "corridor": "",
                    "allocated_qty": ""
                }
                rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False, encoding="utf-8")
    print(f"✨ Tabela caixa/onda salva em {filename} ✨")

def save_stock_usage_table(solution, original_stock, filename):
    used_stock = defaultdict(int)
    for wave in solution:
        for box in wave.boxes:
            sku = box["sku"]
            for floor, corridor, alloc_qty in box.get("corridors", []):
                key = (sku, floor, corridor)
                used_stock[key] += alloc_qty

    rows = []
    for sku, records in original_stock.items():
        for floor, corridor, qty in records:
            key = (sku, floor, corridor)
            used = used_stock.get(key, 0)
            remaining = qty - used
            row = {
                "sku": sku,
                "floor": floor,
                "corridor": corridor,
                "stock_available": qty,
                "stock_used": used,
                "stock_remaining": remaining
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False, encoding="utf-8")
    print(f"📦 Tabela de estoque atualizada salva em {filename} 📦")

# =============================================================================
# Funções para processamento de resíduos
# =============================================================================
def extract_residuals(original_stock, solution):
    allocated_per_sku = defaultdict(int)
    for wave in solution:
        for box in wave.boxes:
            sku = box["sku"]
            allocated_per_sku[sku] += box["pieces"]

    available_per_sku = defaultdict(int)
    for sku, entries in original_stock.items():
        for floor, corridor, qty in entries:
            available_per_sku[sku] += qty

    deficits = {}
    for sku in allocated_per_sku:
        if allocated_per_sku[sku] < available_per_sku.get(sku, 0):
            deficits[sku] = 0
        elif allocated_per_sku[sku] > available_per_sku.get(sku, 0):
            deficits[sku] = allocated_per_sku[sku] - available_per_sku.get(sku, 0)

    return deficits

def create_residual_boxes(location_errors):
    """
    Gera caixas de 'RESIDUO' para o que faltou alocar, a partir dos erros.
    """
    residual_boxes = []
    pattern = re.compile(r"SKU (\S+) no piso (\S+) e corredor (\S+).*Falta (\d+)")
    for err in location_errors:
        m = pattern.search(err)
        if m:
            sku, floor, corridor, deficit = m.groups()
            deficit = int(deficit)
            residual_box = {
                'wave_class': 'RESIDUO',
                'caixa_id': f"res_{sku}_{floor}_{corridor}",
                'pieces': deficit,
                'sku': sku
            }
            residual_boxes.append(residual_box)
    return residual_boxes

def reprocess_residuals(residual_boxes, residual_stock, iterations=10, alpha=0.3, debug_enabled=False):
    solution, _ = grasp_order_batching(
        residual_boxes,
        residual_stock,
        iterations=iterations,
        alpha=alpha,
        debug_enabled=debug_enabled
    )
    return solution

def merge_solutions(sol1, sol2):
    return sol1 + sol2

# =============================================================================
# Função para processar uma única classe de onda
# =============================================================================
def process_wave_class_with_limit(
    wave_class, 
    boxes, 
    stock, 
    iterations,
    alpha,
    debug_enabled,
    max_waves
):
    """
    Processa apenas as caixas de wave_class, usando o GRASP.
    Aplica max_waves como limite de ondas para ESSA classe específica.
    """
    # Filtra as caixas desta classe
    boxes_class = [box for box in boxes if box['wave_class'] == wave_class]

    # Copia do estoque apenas para uso aqui
    stock_class = copy.deepcopy(stock)

    # Aloca as posições de cada caixa (simulate corridores)
    for box in boxes_class:
        box['corridors'] = allocate_sku_combined(box['sku'], box['pieces'], stock_class)

    # Chama o GRASP (que tenta agrupar em ondas)
    solution, logs = grasp_order_batching(
        boxes_class,
        stock_class,
        iterations=iterations,
        alpha=alpha,
        debug_enabled=debug_enabled,
        w_area=1.0,
        w_waves=0.1,
        max_waves=max_waves
    )
    return wave_class, solution, logs

# =============================================================================
# Função de distribuição proporcional das ondas (baseada no número de caixas)
# =============================================================================
def distribute_waves_among_classes(boxes, total_max_waves):
    """
    Dado um total de ondas (total_max_waves), distribui de forma proporcional
    ao número de caixas de cada classe.

    Retorna um dicionário: { wave_class: max_waves_para_essa_classe }
    """
    # 1) Quantas caixas cada classe tem?
    wave_classes = defaultdict(int)
    for box in boxes:
        wave_classes[box['wave_class']] += 1

    classes_list = list(wave_classes.keys())
    class_boxcounts = [wave_classes[c] for c in classes_list]

    n_classes = len(classes_list)
    sum_boxes = sum(class_boxcounts)

    # Se total_max_waves < n_classes, forçamos total_max_waves = n_classes
    if total_max_waves < n_classes:
        total_max_waves = n_classes

    # 2) Distribuição inicial por floor
    waves_distribution = {}
    fractional_parts = []
    for c in classes_list:
        proportion = wave_classes[c] / sum_boxes if sum_boxes > 0 else 1.0
        raw = proportion * total_max_waves
        base = int(floor(raw))  # arredonda para baixo
        if base < 1:
            base = 1  # cada classe precisa de pelo menos 1 onda
        waves_distribution[c] = base
        fractional_parts.append((c, raw - base))  # parte fracionária

    # 3) Ajuste de sobras ou excessos
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

# =============================================================================
# Novo método: cálculo automático do máximo de ondas por classe
# =============================================================================
def calculate_max_waves_by_class(boxes, config):
    """
    Calcula o número máximo de ondas para cada classe, com base no total de caixas
    e em uma configuração de intervalos. A 'config' deve ser uma lista de tuplas:
        (min_count, max_count, caixas_por_onda)
    Exemplo:
        config = [
            (0, 100, 10),      # Se a classe tem 0-100 caixas, usa 10 caixas por onda
            (101, 500, 25),    # Se tem 101-500, usa 25 caixas por onda
            (501, 10000, 50),  # Se tem 501-10000, usa 50 caixas por onda
            (10001, float('inf'), 50)  # Se tem mais de 10000, usa 50 caixas por onda
        ]
    Retorna um dicionário: { wave_class: max_waves }
    """
    counts = defaultdict(int)
    for box in boxes:
        counts[box['wave_class']] += 1

    max_waves_by_class = {}
    for wave_class, total_count in counts.items():
        ratio = None
        for min_count, max_count, caixas_por_onda in config:
            if total_count >= min_count and total_count <= max_count:
                ratio = caixas_por_onda
                break
        # Se nenhum intervalo for encontrado, usa o valor do último intervalo
        if ratio is None:
            ratio = config[-1][2]
        max_waves_by_class[wave_class] = ceil(total_count / ratio)
    return max_waves_by_class

# =============================================================================
# Exemplo de execução: limite fixo e igual p/ todas as classes
# =============================================================================
def rodar_experimentos_ondas_iguais(caixas_csv, estoque_csv, max_waves, iterations=10, alpha=0.3, debug_enabled=False):
    """
    Roda o pipeline onde TODAS as classes têm o MESMO limite de ondas (max_waves).
    """
    print(f"\n=== Rodando com limite igual para todas as classes: max_waves = {max_waves} ===\n")

    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    boxes, stock = preprocess_data(caixas_df, estoque_df)
    original_stock = copy.deepcopy(stock)
    wave_classes = set(box['wave_class'] for box in boxes)

    combined_solution = []
    iteration_logs = []

    for wc in wave_classes:
        _, sol_classe, logs_classe = process_wave_class_with_limit(
            wave_class=wc,
            boxes=boxes,
            stock=stock,
            iterations=iterations,
            alpha=alpha,
            debug_enabled=debug_enabled,
            max_waves=max_waves
        )
        combined_solution.extend(sol_classe)
        iteration_logs.extend(logs_classe)

    total_area = sum(w.area() for w in combined_solution)
    n_waves = len(combined_solution)
    avg_area = total_area / n_waves if n_waves > 0 else 0.0

    print(f"→ {n_waves} ondas geradas (somando todas as classes).")
    print(f"→ Área média final: {avg_area:.2f}")

    valid, errors = validate_solution(combined_solution, boxes, original_stock)
    if not valid:
        print("❌ Erros na validação da solução:")
        for e in errors:
            print(" -", e)
    else:
        print("✅ Solução validada com sucesso.")

    df_logs = pd.DataFrame(iteration_logs)
    df_logs.to_csv(f"logs_ondas_iguais_{max_waves}.csv", index=False)
    print(f"Logs salvos em logs_ondas_iguais_{max_waves}.csv")

# =============================================================================
# Exemplo de execução: limite total p/ todas as classes (distribuição proporcional)
# =============================================================================
def rodar_experimentos_ondas_proporcionais(caixas_csv, estoque_csv, total_max_waves, iterations=10, alpha=0.3, debug_enabled=False):
    """
    Roda o pipeline onde existe um limite TOTAL de ondas (total_max_waves),
    e esse total é distribuído proporcionalmente ao número de caixas de cada classe.
    """
    print(f"\n=== Rodando com limite total = {total_max_waves} (proporcional entre as classes) ===\n")

    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    boxes, stock = preprocess_data(caixas_df, estoque_df)
    original_stock = copy.deepcopy(stock)
    wave_classes = set(box['wave_class'] for box in boxes)

    wave_limits_dict = distribute_waves_among_classes(boxes, total_max_waves)
    print("Distribuição de ondas calculada para cada classe:")
    for wc in wave_limits_dict:
        print(f"  - Classe {wc}: {wave_limits_dict[wc]} ondas (máx.)")

    combined_solution = []
    iteration_logs = []

    for wc in wave_classes:
        class_limit = wave_limits_dict[wc]
        _, sol_classe, logs_classe = process_wave_class_with_limit(
            wave_class=wc,
            boxes=boxes,
            stock=stock,
            iterations=iterations,
            alpha=alpha,
            debug_enabled=debug_enabled,
            max_waves=class_limit
        )
        combined_solution.extend(sol_classe)
        iteration_logs.extend(logs_classe)

    total_area = sum(w.area() for w in combined_solution)
    n_waves = len(combined_solution)
    avg_area = total_area / n_waves if n_waves > 0 else 0.0

    print(f"→ {n_waves} ondas geradas (somando todas as classes).")
    print(f"→ Área média final: {avg_area:.2f}")

    valid, errors = validate_solution(combined_solution, boxes, original_stock)
    if not valid:
        print("❌ Erros na validação da solução:")
        for e in errors:
            print(" -", e)
    else:
        print("✅ Solução validada com sucesso.")

    df_logs = pd.DataFrame(iteration_logs)
    df_logs.to_csv(f"logs_ondas_proporcionais_{total_max_waves}.csv", index=False)
    print(f"Logs salvos em logs_ondas_proporcionais_{total_max_waves}.csv")

# =============================================================================
# Novo método de execução: definição automática do limite de ondas por classe
# com base na proporção esperada (caixas por onda) para intervalos pré-definidos.
# =============================================================================
def rodar_experimentos_ondas_por_config(caixas_csv, estoque_csv, config, iterations=10, alpha=0.3, debug_enabled=False):
    """
    Roda o pipeline onde o máximo de ondas para cada classe é definido automaticamente,
    com base na quantidade de caixas daquela classe e numa configuração de intervalos.
    
    'config' é uma lista de tuplas: (min_count, max_count, caixas_por_onda)
    Exemplo:
        config = [
            (0, 100, 10),      # 0 a 100 caixas: 10 caixas por onda
            (101, 500, 25),    # 101 a 500 caixas: 25 caixas por onda
            (501, 10000, 50),  # 501 a 10.000: 50 caixas por onda
            (10001, float('inf'), 50)
        ]
    """
    print("\n=== Rodando com definição automática do limite de ondas (por configuração) ===\n")

    caixas_df, estoque_df = load_data(caixas_csv, estoque_csv)
    boxes, stock = preprocess_data(caixas_df, estoque_df)
    original_stock = copy.deepcopy(stock)

    # Calcula para cada classe o total de caixas e, com base nisso, o máximo de ondas
    max_waves_dict = calculate_max_waves_by_class(boxes, config)
    print("Máximo de ondas definido para cada classe:")
    for wc in max_waves_dict:
        print(f"  - Classe {wc}: {max_waves_dict[wc]} ondas (máx.), com base em {sum(1 for box in boxes if box['wave_class'] == wc)} caixas.")

    wave_classes = set(box['wave_class'] for box in boxes)
    combined_solution = []
    iteration_logs = []

    for wc in wave_classes:
        class_limit = max_waves_dict[wc]
        _, sol_classe, logs_classe = process_wave_class_with_limit(
            wave_class=wc,
            boxes=boxes,
            stock=stock,
            iterations=iterations,
            alpha=alpha,
            debug_enabled=debug_enabled,
            max_waves=class_limit
        )
        combined_solution.extend(sol_classe)
        iteration_logs.extend(logs_classe)

    total_area = sum(w.area() for w in combined_solution)
    n_waves = len(combined_solution)
    avg_area = total_area / n_waves if n_waves > 0 else 0.0

    print(f"→ {n_waves} ondas geradas (somando todas as classes).")
    print(f"→ Área média final: {avg_area:.2f}")

    valid, errors = validate_solution(combined_solution, boxes, original_stock)
    if not valid:
        print("❌ Erros na validação da solução:")
        for e in errors:
            print(" -", e)
    else:
        print("✅ Solução validada com sucesso.")

    df_logs = pd.DataFrame(iteration_logs)
    df_logs.to_csv("logs_ondas_por_config.csv", index=False)
    print("Logs salvos em logs_ondas_por_config.csv")

# =============================================================================
# Exemplo de uso (main)
# =============================================================================
def main():
    caixas_csv = "data/caixas.csv"
    estoque_csv = "data/estoque.csv"

    # Exemplo 1: Limite fixo para todas as classes
    # rodar_experimentos_ondas_iguais(caixas_csv, estoque_csv, max_waves=100, iterations=5)

    # Exemplo 2: Limite total proporcional
    # rodar_experimentos_ondas_proporcionais(caixas_csv, estoque_csv, total_max_waves=600, iterations=5)

    # Exemplo 3: Definição automática do máximo de ondas por classe com base em uma configuração de caixas por onda
    config = [
        (0, 10, 2),       # Se 0-100 caixas, 10 caixas por onda
        (11, 100, 10),       # Se 0-100 caixas, 10 caixas por onda
        (101, 500, 25),     # Se 101-500, 25 caixas por onda
        (501, 10000, 50),   # Se 501-10000, 50 caixas por onda
        (10001, float('inf'), 50)
    ]
    rodar_experimentos_ondas_por_config(caixas_csv, estoque_csv, config, iterations=5)

if __name__ == "__main__":
    main()
