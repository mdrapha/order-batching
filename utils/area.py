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
