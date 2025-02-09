# grasp/grasp_solver.py
import random
from typing import List, Tuple, Optional
from .wave import Wave
from .allocation import allocate_sku_combined

class GraspSolver:
    """
    Classe que encapsula o algoritmo GRASP para agrupar caixas em ondas.
    """
    def __init__(self, iterations: int = 1, alpha: float = 0.3,
                 w_area: float = 1.0, w_waves: float = 0.1,
                 max_waves: Optional[int] = None, debug: bool = False):
        self.iterations = iterations
        self.alpha = alpha
        self.w_area = w_area
        self.w_waves = w_waves
        self.max_waves = max_waves
        self.debug = debug

    def solve(self, boxes: List[dict], stock: dict) -> Tuple[List[Wave], List[dict]]:
        """
        Executa o GRASP para um conjunto de caixas e retorna a melhor solução e os logs das iterações.
        """
        for box in boxes:
            box["assigned_wave"] = None

        best_solution = None
        best_avg_area = float('inf')
        iteration_logs = []

        sorted_boxes = sorted(boxes, key=lambda x: -len(x.get("corridors", [])))
        for it in range(self.iterations):
            # Reseta as alocações para a iteração atual
            for box in sorted_boxes:
                box["assigned_wave"] = None

            waves = []
            for box in sorted_boxes:
                if box.get("assigned_wave") is not None:
                    continue

                current_waves_count = len(waves)
                feasible_waves = [
                    w for w in waves
                    if w.wave_class == box["wave_class"]
                    and w.total_pieces + box["pieces"] <= 6000
                ]
                candidates = []
                for wave in feasible_waves:
                    wave.add_box(box, simulate=True)
                    new_area = wave.area()
                    wave.remove_box(box, simulate=True)
                    metric = self.w_area * new_area + self.w_waves * current_waves_count
                    candidates.append((metric, wave, False))
                can_create_new = self.max_waves is None or current_waves_count < self.max_waves
                if can_create_new:
                    new_wave = Wave(box["wave_class"], debug_enabled=self.debug)
                    new_wave.add_box(box, simulate=False)
                    metric_new = self.w_area * new_wave.area() + self.w_waves * (current_waves_count + 1)
                    candidates.append((metric_new, new_wave, True))
                if not candidates:
                    continue
                min_val = min(c[0] for c in candidates)
                max_val = max(c[0] for c in candidates)
                threshold = min_val + self.alpha * (max_val - min_val)
                rcl = [c for c in candidates if c[0] <= threshold]
                chosen_metric, selected_wave, is_new = random.choice(rcl)
                if is_new:
                    waves.append(selected_wave)
                else:
                    selected_wave.add_box(box, simulate=False)
            total_area = sum(w.area() for w in waves)
            avg_area = total_area / len(waves) if waves else float("inf")
            if avg_area < best_avg_area:
                best_avg_area = avg_area
                best_solution = list(waves)
            iteration_logs.append({
                "iteration": it + 1,
                "best_avg_area": best_avg_area,
                "n_waves": len(waves)
            })
        return best_solution, iteration_logs
