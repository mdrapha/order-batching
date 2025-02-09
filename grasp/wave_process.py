from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
from grasp.allocation import allocate_sku_combined
from grasp.grasp import grasp_order_batching

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
    Processa as caixas de uma wave_class usando o GRASP com limite de ondas.
    """
    boxes_class = [box for box in boxes if box['wave_class'] == wave_class]
    stock_class = copy.deepcopy(stock)
    for box in boxes_class:
        box['corridors'] = allocate_sku_combined(box['sku'], box['pieces'], stock_class)
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
