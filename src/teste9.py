import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

def calcular_area_classe(uso_corredores_por_andar):
    """
    Exemplo básico de área = sum((c_max - c_min) por andar).
    """
    area_total = 0
    for andar, (c_min, c_max) in uso_corredores_por_andar.items():
        area_total += (c_max - c_min)
    return area_total

def atualizar_area_classe(uso_corredores_por_andar, andar, corredor):
    if andar not in uso_corredores_por_andar:
        uso_corredores_por_andar[andar] = (corredor, corredor)
    else:
        c_min, c_max = uso_corredores_por_andar[andar]
        c_min = min(c_min, corredor)
        c_max = max(c_max, corredor)
        uso_corredores_por_andar[andar] = (c_min, c_max)

def construir_sku_corredores_aninhado(estoque):
    sku_corredores = {}
    for _, row in estoque.iterrows():
        sku = row['SKU']
        andar = row['ANDAR']
        corredor = row['CORREDOR']
        pecas = row['PECAS']
        if sku not in sku_corredores:
            sku_corredores[sku] = {}
        if andar not in sku_corredores[sku]:
            sku_corredores[sku][andar] = []
        sku_corredores[sku][andar].append({'CORREDOR': corredor, 'PECAS': pecas})
    # Ordenar cada lista (por PECAS desc, corredor asc)
    for sku in sku_corredores:
        for andar in sku_corredores[sku]:
            sku_corredores[sku][andar].sort(key=lambda x: (-x['PECAS'], x['CORREDOR']))
    return sku_corredores

def decrementa_estoque(sku_corredores, sku, andar, corredor, qtd):
    if sku not in sku_corredores:
        return
    if andar not in sku_corredores[sku]:
        return
    lista_ = sku_corredores[sku][andar]
    for i, info in enumerate(lista_):
        if info['CORREDOR'] == corredor:
            info['PECAS'] -= qtd
            if info['PECAS'] <= 0:
                lista_.pop(i)
            break
    if len(lista_) == 0:
        sku_corredores[sku].pop(andar, None)

def encontrar_corredores_suficientes(sku_corredores, sku, qtd):
    """
    Retorna lista de {ANDAR, CORREDOR, PECAS} com PECAS >= qtd, 
    varrendo todos os andares desse SKU.
    """
    if sku not in sku_corredores:
        return []
    resultado = []
    for andar, lista_cor in sku_corredores[sku].items():
        for info in lista_cor:
            if info['PECAS'] < qtd:
                break  # pois já está ordenado
            resultado.append({'ANDAR': andar, 'CORREDOR': info['CORREDOR'], 'PECAS': info['PECAS']})
    return resultado

def best_fit_for_skus(skus_pecas, sku_corredores, uso_corredores_por_andar):
    """
    Tenta alocar cada SKU (ordenado por qtd desc) no corredor “mais próximo” 
    do miolo (média) de todos os corredores já usados.
    
    Retorna: 
      alocacoes -> lista (andar, corredor, sku, qtd)
      skus_restantes -> dicionário {sku: qtd} não alocados
    """
    # Ordenar SKUs por qtd desc
    skus_ordenados = sorted(skus_pecas.items(), key=lambda x: x[1], reverse=True)
    alocacoes = []
    skus_restantes = {}

    for sku, qtd_needed in skus_ordenados:
        corredores_possiveis = encontrar_corredores_suficientes(sku_corredores, sku, qtd_needed)
        if not corredores_possiveis:
            skus_restantes[sku] = qtd_needed
            continue
        # Calcular “miolo”
        if uso_corredores_por_andar:
            all_c_mins = [v[0] for v in uso_corredores_por_andar.values()]
            all_c_maxs = [v[1] for v in uso_corredores_por_andar.values()]
            c_min_global = min(all_c_mins)
            c_max_global = max(all_c_maxs)
            media_corr = (c_min_global + c_max_global) / 2.0
        else:
            media_corr = 0

        melhor_corr = None
        melhor_dist = float('inf')
        for cinfo in corredores_possiveis:
            dist_ = abs(cinfo['CORREDOR'] - media_corr)
            if dist_ < melhor_dist:
                melhor_dist = dist_
                melhor_corr = cinfo

        if melhor_corr:
            andar_ = melhor_corr['ANDAR']
            cor_   = melhor_corr['CORREDOR']
            # Alocar
            atualizar_area_classe(uso_corredores_por_andar, andar_, cor_)
            decrementa_estoque(sku_corredores, sku, andar_, cor_, qtd_needed)
            alocacoes.append((andar_, cor_, sku, qtd_needed))
        else:
            skus_restantes[sku] = qtd_needed

    return alocacoes, skus_restantes

def fallback_for_skus(skus_pecas, sku_corredores, uso_corredores_por_andar):
    """
    Fallback - atende sem se preocupar muito com a área, 
    mas ainda atualizando o uso_corredores_por_andar.
    
    Retorna lista de (andar, corredor, sku, qtd).
    """
    resultado = []
    for sku, qtd_needed in skus_pecas.items():
        qtd_rest = qtd_needed
        if sku not in sku_corredores:
            logging.error(f"[Fallback] SKU {sku} não existe.")
            continue
        for andar in list(sku_corredores[sku].keys()):
            lista_ = sku_corredores[sku][andar]
            i = 0
            while i < len(lista_):
                info = lista_[i]
                if info['PECAS'] > 0:
                    qtd_possivel = min(info['PECAS'], qtd_rest)
                    info['PECAS'] -= qtd_possivel
                    qtd_rest -= qtd_possivel
                    atualizar_area_classe(uso_corredores_por_andar, andar, info['CORREDOR'])
                    resultado.append((andar, info['CORREDOR'], sku, qtd_possivel))
                    if info['PECAS'] <= 0:
                        lista_.pop(i)
                        i -= 1
                    if qtd_rest <= 0:
                        break
                i += 1
            if len(lista_) == 0:
                sku_corredores[sku].pop(andar, None)
            if qtd_rest <= 0:
                break
        if qtd_rest > 0:
            logging.error(f"[Fallback] Não foi possível atender {sku}, rest={qtd_rest}")
    return resultado

def processar_caixa_best_fit(caixa_id, caixas_classe, sku_corredores, uso_corredores_por_andar):
    """
    Faz o approach Best-Fit para 1 caixa:
      1) Single-corridor: se há 1 corredor que supra todos SKUs
      2) Caso contrário, multi-corr Best-Fit
      3) Fallback para o que faltar
    Retorna: lista de (andar, corredor, sku, qtd) ou None
    """
    df = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
    skus_pecas = df.groupby('SKU')['PECAS'].sum().to_dict()

    # Verificar single-corr
    sets_corr = []
    for sku, qtd_needed in skus_pecas.items():
        poss = encontrar_corredores_suficientes(sku_corredores, sku, qtd_needed)
        set_poss = set((p['ANDAR'], p['CORREDOR']) for p in poss)
        sets_corr.append(set_poss)
    if sets_corr:
        intersec = set.intersection(*sets_corr)
    else:
        intersec = set()
    if intersec:
        # Single-corr
        # Escolher “melhor” corredor (ex.: menor dist do centro)
        # Para simplificar, pego o “primeiro da intersec”
        melhor_c = None
        melhor_d = float('inf')
        if uso_corredores_por_andar:
            all_c_mins = [v[0] for v in uso_corredores_por_andar.values()]
            all_c_maxs = [v[1] for v in uso_corredores_por_andar.values()]
            c_min_global = min(all_c_mins)
            c_max_global = max(all_c_maxs)
            media_corr = (c_min_global + c_max_global)/2.0
        else:
            media_corr = 0

        for (a_, c_) in intersec:
            dist_ = abs(c_ - media_corr)
            if dist_ < melhor_d:
                melhor_d = dist_
                melhor_c = (a_, c_)
        # Alocar
        if melhor_c:
            a__, c__ = melhor_c
            for sku, qtd_needed in skus_pecas.items():
                decrementa_estoque(sku_corredores, sku, a__, c__, qtd_needed)
            atualizar_area_classe(uso_corredores_por_andar, a__, c__)
            # retorna
            return [('single-corr', a__, c__, skus_pecas)]
        else:
            # fallback
            # Aqui poderíamos mandar p/ multi-corr ...
            pass

    # Se não for single-corr, faz Best-Fit
    aloc, restos = best_fit_for_skus(skus_pecas, sku_corredores, uso_corredores_por_andar)
    if restos:
        # fallback
        fb = fallback_for_skus(restos, sku_corredores, uso_corredores_por_andar)
        aloc.extend(fb)
    return aloc

def organizar_caixas_por_classe(caixas):
    classes = {}
    for c_onda, group in caixas.groupby('CLASSE_ONDA'):
        classes[c_onda] = group.copy()
    return classes

def main():
    caixas = pd.read_csv("data/caixas.csv")
    estoque = pd.read_csv("data/estoque.csv")

    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()

    sku_corredores = construir_sku_corredores_aninhado(estoque)
    caixas_por_classe = organizar_caixas_por_classe(caixas)

    resultados = {}
    for classe_onda, df_caixas in caixas_por_classe.items():
        print(f"\n=== Classe de onda: {classe_onda} (Best Fit) ===")
        uso_corredores_por_andar = {}
        caixa_ids = df_caixas['CAIXA_ID'].unique()
        solucoes_classe = {}
        for c_id in tqdm(caixa_ids, desc=f"Processando caixas da classe {classe_onda}"):
            sol = processar_caixa_best_fit(c_id, df_caixas, sku_corredores, uso_corredores_por_andar)
            solucoes_classe[c_id] = sol

        area_final = calcular_area_classe(uso_corredores_por_andar)
        resultados[classe_onda] = {
            'solucoes': solucoes_classe,
            'area_final': area_final,
            'uso_corredores_por_andar': uso_corredores_por_andar
        }

    print("\n=== RESULTADOS (Best Fit) ===")
    for classe_onda, info in resultados.items():
        print(f"Classe {classe_onda}: área final = {info['area_final']:.2f}")
        # Exemplo de exibição de andares
        for andar, (cmin, cmax) in info['uso_corredores_por_andar'].items():
            total_corr = (cmax - cmin) + 1
            print(f"  Andar {andar}: c_min={cmin}, c_max={cmax}, total_corr={total_corr}")
    print("\nConcluído (Best Fit).")

if __name__ == "__main__":
    main()