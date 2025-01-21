# methods.py

import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

# Se quiser definir o logging aqui ou no script principal, a seu critério
logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

# Parâmetros default (pode deixar aqui ou no script principal)
TABU_LIMIT = 200
LIMIAR = 3.0

def calcular_area_classe(uso_corredores_por_andar):
    """
    Retorna a soma de (c_max - c_min) para cada andar no dicionário uso_corredores_por_andar.
    """
    area_total = 0
    for _, (c_min, c_max) in uso_corredores_por_andar.items():
        area_total += (c_max - c_min)
    return area_total

def atualizar_area_classe(uso_corredores_por_andar, andar, corredor):
    """
    Atualiza (c_min, c_max) para o andar em uso_corredores_por_andar, 
    levando em conta o novo corredor.
    """
    if andar not in uso_corredores_por_andar:
        uso_corredores_por_andar[andar] = (corredor, corredor)
    else:
        c_min, c_max = uso_corredores_por_andar[andar]
        c_min = min(c_min, corredor)
        c_max = max(c_max, corredor)
        uso_corredores_por_andar[andar] = (c_min, c_max)

def calcular_area_se_incluir(uso_corredores_por_andar, andar, corredor):
    """
    Retorna a área total se incluirmos (andar, corredor) temporariamente,
    sem alterar permanentemente uso_corredores_por_andar.
    """
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
    """
    Constrói um dicionário aninhado:
      sku_corredores[SKU][ANDAR] = [ { 'CORREDOR': X, 'PECAS': Y }, ...]
    e ordena cada lista por (PECAS desc, CORREDOR asc).
    """
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

    # Ordenar
    for sku in sku_corredores:
        for andar in sku_corredores[sku]:
            sku_corredores[sku][andar].sort(key=lambda x: (-x['PECAS'], x['CORREDOR']))
    return sku_corredores

def decrementa_estoque(sku_corredores, sku, andar, corredor, qtd):
    """
    Decrementa 'qtd' do corredor específico em sku_corredores[sku][andar].
    Remove se ficar <= 0.
    """
    if sku not in sku_corredores:
        return
    if andar not in sku_corredores[sku]:
        return
    corredores_list = sku_corredores[sku][andar]
    for i, info in enumerate(corredores_list):
        if info['CORREDOR'] == corredor:
            info['PECAS'] -= qtd
            if info['PECAS'] <= 0:
                corredores_list.pop(i)
            break
    if len(corredores_list) == 0:
        sku_corredores[sku].pop(andar, None)

def encontrar_corredores_suficientes(sku_corredores, sku, qtd):
    """
    Retorna [ { 'ANDAR': A, 'CORREDOR': C, 'PECAS': P}, ...]
    onde P >= qtd, percorrendo o dicionário aninhado do SKU.
    """
    if sku not in sku_corredores:
        return []
    resultado = []
    for andar, lista_cor in sku_corredores[sku].items():
        for info in lista_cor:
            if info['PECAS'] < qtd:
                break
            resultado.append({
                'ANDAR': andar,
                'CORREDOR': info['CORREDOR'],
                'PECAS': info['PECAS']
            })
    return resultado

def escolher_corredor_tabu(sku, qtd_needed, uso_corredores_por_andar, sku_corredores,
                           tabu_limit=TABU_LIMIT, limiar=LIMIAR):
    """
    Tenta achar o corredor que menos aumenta a área.
    Se o melhor aumento > limiar, tentamos as próximas 'tabu_limit' candidatas
    para ver se alguma é melhor ou não tão pior.
    """
    poss = encontrar_corredores_suficientes(sku_corredores, sku, qtd_needed)
    if not poss:
        return None

    candidatas = []
    area_atual = calcular_area_classe(uso_corredores_por_andar)
    for c in poss:
        andar_ = c['ANDAR']
        cor_   = c['CORREDOR']
        area_incluir_ = calcular_area_se_incluir(uso_corredores_por_andar, andar_, cor_)
        aumento = area_incluir_ - area_atual
        candidatas.append((c, aumento))

    # Ordenar por aumento asc
    candidatas.sort(key=lambda x: x[1])

    melhor_cinfo, melhor_aumento = candidatas[0]
    if melhor_aumento <= limiar:
        return melhor_cinfo
    else:
        for i in range(1, min(tabu_limit, len(candidatas))):
            cinfo_i, aumento_i = candidatas[i]
            if aumento_i < melhor_aumento * 1.2:
                return cinfo_i
        return melhor_cinfo

def fallback_for_skus(skus_necessarios, sku_corredores, uso_corredores_por_andar):
    """
    Força o atendimento de cada SKU, independentemente de área,
    mas atualizando uso_corredores_por_andar (para refletir o picking).
    """
    resultado = []
    for sku, qtd_needed in skus_necessarios.items():
        qtd_rest = qtd_needed
        if sku not in sku_corredores:
            logging.error(f"[Fallback] SKU {sku} não existe no dicionário.")
            continue
        # Tenta esvaziar progressivamente
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
            logging.error(f"[Fallback] Falha parcial no SKU {sku}, rest={qtd_rest}")
    return resultado

def processar_caixa_tabu(caixa_id, df_caixas, sku_corredores, uso_corredores_por_andar,
                         tabu_limit=TABU_LIMIT, limiar=LIMIAR):
    """
    1) Tenta single-corr (ver se existe 1 corredor que supra todos os SKUs)
    2) Senão, multi-corr (Tabu)
    3) Se ainda restar algo, fallback
    Retorna uma lista ou info do que foi feito (para debug).
    """
    df_ = df_caixas[df_caixas['CAIXA_ID'] == caixa_id]
    skus_pecas = df_.groupby('SKU')['PECAS'].sum().to_dict()

    # Tenta single-corr
    sets_corr = []
    for sku, qtd_needed in skus_pecas.items():
        poss = encontrar_corredores_suficientes(sku_corredores, sku, qtd_needed)
        set_poss = set((p['ANDAR'], p['CORREDOR']) for p in poss)
        sets_corr.append(set_poss)

    intersec = set.intersection(*sets_corr) if sets_corr else set()
    if intersec:
        area_atual = calcular_area_classe(uso_corredores_por_andar)
        melhor_corr = None
        melhor_inc  = float('inf')
        for (a_, c_) in intersec:
            area_incl_ = calcular_area_se_incluir(uso_corredores_por_andar, a_, c_)
            inc_ = area_incl_ - area_atual
            if inc_ < melhor_inc:
                melhor_inc = inc_
                melhor_corr = (a_, c_)
        if melhor_corr:
            a__, c__ = melhor_corr
            # Decrementa
            for sku, qtd_ in skus_pecas.items():
                decrementa_estoque(sku_corredores, sku, a__, c__, qtd_)
            atualizar_area_classe(uso_corredores_por_andar, a__, c__)
            return [('single-corr', a__, c__, skus_pecas)]

    # Multi-corr Tabu
    alocacoes = []
    skus_restantes = {}
    for sku, qtd_ in skus_pecas.items():
        cinfo = escolher_corredor_tabu(sku, qtd_, uso_corredores_por_andar, sku_corredores,
                                       tabu_limit=tabu_limit, limiar=limiar)
        if not cinfo:
            skus_restantes[sku] = qtd_
            continue
        andar_ = cinfo['ANDAR']
        cor_   = cinfo['CORREDOR']
        atualizar_area_classe(uso_corredores_por_andar, andar_, cor_)
        decrementa_estoque(sku_corredores, sku, andar_, cor_, qtd_)
        alocacoes.append((andar_, cor_, sku, qtd_))

    if skus_restantes:
        fb = fallback_for_skus(skus_restantes, sku_corredores, uso_corredores_por_andar)
        alocacoes.extend(fb)

    return alocacoes

def organizar_caixas_por_classe(caixas):
    """
    Retorna { classe_onda: df_com_aquela_classe }
    """
    classes = {}
    for c_onda, group in caixas.groupby('CLASSE_ONDA'):
        classes[c_onda] = group.copy()
    return classes