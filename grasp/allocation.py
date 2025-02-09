# grasp/allocation.py

from collections import defaultdict

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
        return allocate_sku_new(sku, required, stock)

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
