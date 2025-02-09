# utils/iotools.py

import pandas as pd
from collections import defaultdict

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
    result = allocate_sku_old(sku, required, stock)
    if result is not None:
        return result
    else:
        result = allocate_sku_new(sku, required, stock)
        return result
    
def save_iteration_logs_csv(logs, filename):
    df_logs = pd.DataFrame(logs)
    df_logs.to_csv(filename, index=False, encoding="utf-8")
    print(f"📝 Logs das iterações salvos em {filename}")

# =============================================================================
# Função para imprimir resumo dos resultados a partir do CSV de logs
# =============================================================================
def print_summary_results(logs_csv):
    df = pd.read_csv(logs_csv)
    if df.empty:
        print("⚠️ Nenhum log encontrado!")
        return
    print("\n🎉 Resumo Final dos Resultados por Classe de Onda 🎉")
    grouped = df.groupby("wave_class")
    for wave_class, group in grouped:
        group_sorted = group.sort_values(by="iteration")
        first = group_sorted.iloc[0]
        last = group_sorted.iloc[-1]
        improvement = first["best_avg_area"] - last["best_avg_area"]
        improvement_pct = (improvement / first["best_avg_area"]) * 100 if first["best_avg_area"] != 0 else 0
        print(f"\n🔹 Classe {wave_class}:")
        print(f"   Iteração Inicial: {int(first['iteration'])} | Área Média: {first['best_avg_area']:.2f} | Ondas: {int(first['n_waves'])} | Caixas: {int(first['n_boxes'])}")
        print(f"   Iteração Final  : {int(last['iteration'])} | Área Média: {last['best_avg_area']:.2f} | Ondas: {int(last['n_waves'])} | Caixas: {int(last['n_boxes'])}")
        print(f"   Melhoria: {improvement:.2f} ({improvement_pct:.1f}%) 💪")
    print("\n🚀 Fim do resumo. Parabéns! 🎊\n")

def save_box_wave_table(solution, filename):
    rows = []
    for idx, wave in enumerate(solution, start=1):
        wave_id = f"Onda {idx}"
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