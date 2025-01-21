import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

# Parâmetro de "tabu"
TABU_LIMIT = 200   # Tentar 3 opções subótimas
LIMIAR = 3.0    # Se o melhor aumento for maior que 50, tentamos rollback

def calcular_area_classe(uso_corredores_por_andar):
    area_total = 0
    for _, (c_min, c_max) in uso_corredores_por_andar.items():
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

def calcular_area_se_incluir(uso_corredores_por_andar, andar, corredor):
    temp_uso = dict(uso_corredores_por_andar)
    if andar not in temp_uso:
        temp_uso[andar] = (corredor, corredor)
    else:
        c_min, c_max = temp_uso[andar]
        c_min = min(c_min, corredor)
        c_max = max(c_max, corredor)
        temp_uso[andar] = (c_min, c_max)
    return calcular_area_classe(temp_uso)

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
    if sku not in sku_corredores:
        return []
    resultado = []
    for andar, lista_cor in sku_corredores[sku].items():
        for info in lista_cor:
            if info['PECAS'] < qtd:
                break
            resultado.append({'ANDAR': andar, 'CORREDOR': info['CORREDOR'], 'PECAS': info['PECAS']})
    return resultado

def escolher_corredor_tabu(sku, qtd_needed, uso_corredores_por_andar, sku_corredores):
    """
    Similar ao "menor aumento de área",
    mas se o 'melhor' for muito grande, tentamos as próximas 2-3 opções.
    """
    poss = encontrar_corredores_suficientes(sku_corredores, sku, qtd_needed)
    if not poss:
        return None

    # Calcular (aumento, cinfo)
    candidatas = []
    area_atual = calcular_area_classe(uso_corredores_por_andar)
    for c in poss:
        andar_ = c['ANDAR']
        cor_   = c['CORREDOR']
        area_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar_, cor_)
        aumento = area_incluir - area_atual
        candidatas.append((c, aumento))

    # Ordenar por aumento asc
    candidatas.sort(key=lambda x: x[1])

    melhor_cinfo, melhor_aumento = candidatas[0]
    if melhor_aumento <= LIMIAR:
        return melhor_cinfo
    else:
        # Tenta as próximas 'TABU_LIMIT'
        for i in range(1, min(TABU_LIMIT, len(candidatas))):
            cinfo_i, aumento_i = candidatas[i]
            # Se esse 'aumento_i' for não muito maior que 'melhor_aumento'
            # ou for abaixo do LIMIAR, escolher
            if aumento_i < melhor_aumento * 1.2:
                return cinfo_i
        # se nada melhor, pega a melhor
        return melhor_cinfo

def fallback_for_skus(skus_pecas, sku_corredores, uso_corredores_por_andar):
    resultado = []
    for sku, qtd_needed in skus_pecas.items():
        qtd_rest = qtd_needed
        if sku not in sku_corredores:
            logging.error(f"[Fallback] SKU {sku} inexistente.")
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
            logging.error(f"[Fallback] Falha em {sku}, rest={qtd_rest}")
    return resultado

def processar_caixa_tabu(caixa_id, df_caixas, sku_corredores, uso_corredores_por_andar):
    """
    1) Tenta single-corr
    2) Se falhar => multi-corr com 'escolher_corredor_tabu'
    3) Se ainda faltar => fallback
    """
    df_ = df_caixas[df_caixas['CAIXA_ID'] == caixa_id]
    skus_pecas = df_.groupby('SKU')['PECAS'].sum().to_dict()

    # Single-corr?
    sets_corr = []
    for sku, qtd in skus_pecas.items():
        poss = encontrar_corredores_suficientes(sku_corredores, sku, qtd)
        set_poss = set((p['ANDAR'], p['CORREDOR']) for p in poss)
        sets_corr.append(set_poss)
    if sets_corr:
        intersec = set.intersection(*sets_corr)
    else:
        intersec = set()
    if intersec:
        # escolher "melhor"
        area_atual = calcular_area_classe(uso_corredores_por_andar)
        melhor_corr = None
        melhor_inc  = float('inf')
        for (a_, c_) in intersec:
            area_incl = calcular_area_se_incluir(uso_corredores_por_andar, a_, c_)
            inc = area_incl - area_atual
            if inc < melhor_inc:
                melhor_inc = inc
                melhor_corr = (a_, c_)
        if melhor_corr:
            a__, c__ = melhor_corr
            for sku, qtd in skus_pecas.items():
                decrementa_estoque(sku_corredores, sku, a__, c__, qtd)
            atualizar_area_classe(uso_corredores_por_andar, a__, c__)
            return [('single-corr', a__, c__, skus_pecas)]
        # else, cair p/ multi-corr
    # multi-corr com 'tabu'
    alocacoes = []
    skus_restantes = {}
    for sku, qtd in skus_pecas.items():
        cinfo = escolher_corredor_tabu(sku, qtd, uso_corredores_por_andar, sku_corredores)
        if not cinfo:
            skus_restantes[sku] = qtd
            continue
        andar_ = cinfo['ANDAR']
        cor_   = cinfo['CORREDOR']
        atualizar_area_classe(uso_corredores_por_andar, andar_, cor_)
        decrementa_estoque(sku_corredores, sku, andar_, cor_, qtd)
        alocacoes.append((andar_, cor_, sku, qtd))

    if skus_restantes:
        # fallback
        fb = fallback_for_skus(skus_restantes, sku_corredores, uso_corredores_por_andar)
        alocacoes.extend(fb)
    return alocacoes

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
        print(f"\n=== Classe {classe_onda} (Tabu Approach) ===")
        uso_corredores_por_andar = {}
        solucoes_classe = {}
        for caixa_id in tqdm(df_caixas['CAIXA_ID'].unique(), desc=f"Processo {classe_onda}"):
            sol = processar_caixa_tabu(caixa_id, df_caixas, sku_corredores, uso_corredores_por_andar)
            solucoes_classe[caixa_id] = sol
        area_final = calcular_area_classe(uso_corredores_por_andar)
        resultados[classe_onda] = {
            'solucoes': solucoes_classe,
            'area_final': area_final,
            'uso_corredores_por_andar': uso_corredores_por_andar
        }

    print("\n=== RESULTADOS (Tabu Approach) ===")
    for classe_onda, info in resultados.items():
        print(f"Classe {classe_onda}: area_final = {info['area_final']:.2f}")
        for andar_, (cmin, cmax) in info['uso_corredores_por_andar'].items():
            total_corr_ = (cmax - cmin) + 1
            print(f"  Andar {andar_}: c_min={cmin}, c_max={cmax}, total_corr={total_corr_}")
    print("\nConcluído (Tabu Approach).")

if __name__ == "__main__":
    main()