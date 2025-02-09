# =============================================================================
# Funções de validação e salvamento
# =============================================================================
from collections import defaultdict


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
            errors.append(f"Para SKU {sku} no piso {floor} e corredor {corridor}, foram utilizadas {used} peças, mas o estoque disponível é {available}. Falta {deficit} peças.")
    return errors

def validate_solution(solution, all_boxes, original_stock):
    errors = []
    for wave in solution:
        soma_pieces = sum(box["pieces"] for box in wave.boxes)
        if soma_pieces != wave.total_pieces:
            errors.append(f"Onda {wave.wave_class}: soma das peças ({soma_pieces}) difere do total ({wave.total_pieces}).")
    sku_usage = defaultdict(int)
    for wave in solution:
        for box in wave.boxes:
            sku_usage[box["sku"]] += box["pieces"]
    for sku, total_used in sku_usage.items():
        total_available = sum(qty for _, _, qty in original_stock.get(sku, []))
        if total_used > total_available:
            errors.append(f"SKU {sku}: utilizado {total_used} peças, mas estoque disponível é {total_available}.")
    solution[:] = [wave for wave in solution if wave.boxes]
    valid = (len(errors) == 0)
    return valid, errors