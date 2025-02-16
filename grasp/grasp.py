import random
import time
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
    # Ordena as caixas com base no número de possíveis corridors (decrescente)
    sorted_boxes = sorted(boxes, key=lambda x: -len(x.get('corridors', [])))
    iteration_logs = []
    
    start_time = time.time()  # Inicia a medição do tempo de execução

    for it in range(iterations):
        # Reseta a alocação para cada caixa para a iteração atual
        for box in sorted_boxes:
            box["assigned_wave"] = None
        # Conjunto para rastrear caixas já alocadas (usando caixa_id)
        allocated_box_ids = set()
        waves = []
        for box in sorted_boxes:
            # Se a caixa já foi alocada, pule
            if box.get("caixa_id") in allocated_box_ids:
                continue
            if box.get("assigned_wave") is not None:
                allocated_box_ids.add(box["caixa_id"])
                continue
            
            current_waves_count = len(waves)
            candidates = []
            # Procura por ondas existentes da mesma classe que possam receber a caixa inteira
            feasible_waves = [w for w in waves 
                              if w.wave_class == box['wave_class'] and w.total_pieces + box['pieces'] <= 6000]
            for wave in feasible_waves:
                # Simulação: tenta inserir a caixa sem modificar o estado definitivo
                if wave.add_box(box, simulate=True):
                    new_area = wave.area()
                    wave.remove_box(box, simulate=True)
                    metric = w_area * new_area + w_waves * current_waves_count
                    candidates.append((metric, wave, False))  # False indica que a caixa seria alocada em uma onda existente
            # Se permitido, tenta criar uma nova onda
            can_create_new = True
            if (max_waves is not None) and (current_waves_count >= max_waves):
                can_create_new = False
            if can_create_new:
                new_wave = Wave(box['wave_class'], debug_enabled=debug_enabled)
                # Tenta adicionar a caixa definitivamente à nova onda
                if new_wave.add_box(box, simulate=False):
                    metric_new = w_area * new_wave.area() + w_waves * (current_waves_count + 1)
                    candidates.append((metric_new, new_wave, True))  # True indica nova onda
            # Se não houver candidatos, a caixa não foi alocada nesta iteração
            if not candidates:
                continue
            min_val = min(cand[0] for cand in candidates)
            max_val = max(cand[0] for cand in candidates)
            threshold = min_val + alpha * (max_val - min_val)
            rcl = [cand for cand in candidates if cand[0] <= threshold]
            chosen_metric, selected_wave, is_new = random.choice(rcl)
            # Se a caixa ainda não tiver sido alocada, finaliza a alocação
            if box.get("assigned_wave") is None:
                if not is_new:
                    if selected_wave.add_box(box, simulate=False):
                        allocated_box_ids.add(box["caixa_id"])
                else:
                    # A nova onda já recebeu a caixa em modo definitivo
                    waves.append(selected_wave)
                    allocated_box_ids.add(box["caixa_id"])
        total_area = sum(w.area() for w in waves)
        n_waves = len(waves)
        avg_area = total_area / n_waves if n_waves > 0 else float('inf')
        if avg_area < best_avg_area:
            best_avg_area = avg_area
            best_solution = [w for w in waves]
        iteration_logs.append({
            "wave_class": sorted_boxes[0]['wave_class'] if sorted_boxes else None,
            "iteration": it + 1,
            "best_avg_area": best_avg_area,
            "n_waves": n_waves,
            "n_boxes": len(sorted_boxes)
        })
    end_time = time.time()
    total_time = end_time - start_time
    print(f"Tempo total de execução: {total_time:.2f} segundos")
    iteration_logs.append({"total_execution_time": total_time})
    return best_solution, iteration_logs
