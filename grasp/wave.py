from collections import defaultdict
import time
from utils.area import area_side

class DebugLogger:
    def __init__(self, max_lines=5, enable=False):
        self.max_lines = max_lines
        self.enable = enable

    def log(self, message):
        if self.enable:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")

def default_floor():
    return {'par': defaultdict(int), 'impar': defaultdict(int)}

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
            # Remove o andar se não houver mais caixas (sem entradas em 'par' e 'impar')
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
