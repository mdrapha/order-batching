# =============================================================================
# Funções para processamento de resíduos
# =============================================================================
from collections import defaultdict
import re

from grasp.grasp import grasp_order_batching


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

def reprocess_residuals(residual_boxes, residual_stock, iterations=1, alpha=0.3, debug_enabled=False):
    solution, _ = grasp_order_batching(residual_boxes, residual_stock, iterations=iterations, alpha=alpha, debug_enabled=debug_enabled)
    return solution

def merge_solutions(sol1, sol2):
    return sol1 + sol2