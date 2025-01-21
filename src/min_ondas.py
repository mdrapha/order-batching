import math
import pandas as pd

caixas = pd.read_csv("data/caixas.csv")
estoque = pd.read_csv("data/estoque.csv")

# 1) Calcular o total de itens em todas as caixas
total_itens = caixas['PECAS'].sum()

# 2) Dividir por 6000 e arredondar para cima (ceil),
#    pois mesmo que sobrem poucas peças, é preciso uma onda extra.
minimo_ondas = math.ceil(total_itens / 6000)

print(f"Total de itens: {total_itens}")
print(f"Mínimo de ondas necessárias (sem misturar classes): {minimo_ondas}")