import random
from grasp.wave import Wave

def grasp_order_batching(
    boxes,
    stock,
    iterations=1,
    alpha=0.3,
    max_local_iterations=10,
    debug_enabled=False,
    w_area=1.0,
    w_waves=0.1,
    max_waves=None  # se não for None, limita o nº de ondas criadas
):
    best_solution = None
    best_avg_area = float('inf')
    sorted_boxes = sorted(boxes, key=lambda x: -len(x.get('corridors', [])))
    iteration_logs = []

    for it in range(iterations):
        # Reseta a alocação para cada caixa
        for box in sorted_boxes:
            box["assigned_wave"] = None
        waves = []
        for box in sorted_boxes:
            if box.get("assigned_wave") is not None:
                continue  # caixa já alocada
            current_waves_count = len(waves)
            # Ondas existentes que ainda podem receber a caixa
            feasible_waves = [
                w for w in waves
                if w.wave_class == box['wave_class']
                and w.total_pieces + box['pieces'] <= 6000
            ]
            candidates = []
            # Tenta inserir em cada onda existente
            for wave in feasible_waves:
                wave.add_box(box, simulate=True)
                new_area = wave.area()
                wave.remove_box(box, simulate=True)
                metric = w_area * new_area + w_waves * current_waves_count
                candidates.append((metric, wave, False))  # False = onda existente
            # Se permitido, tenta criar uma nova onda
            can_create_new = True
            if (max_waves is not None) and (current_waves_count >= max_waves):
                can_create_new = False
            if can_create_new:
                new_wave = Wave(box['wave_class'], debug_enabled=debug_enabled)
                new_wave.add_box(box, simulate=False)
                metric_new = w_area * new_wave.area() + w_waves * (current_waves_count + 1)
                candidates.append((metric_new, new_wave, True))  # True = nova onda
            if not candidates:
                continue
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
            best_solution = [w for w in waves]
        iteration_logs.append({
            "wave_class": sorted_boxes[0]['wave_class'] if sorted_boxes else None,
            "iteration": it + 1,
            "best_avg_area": best_avg_area,
            "n_waves": len(waves),
            "n_boxes": len(sorted_boxes)
        })
    return best_solution, iteration_logs
