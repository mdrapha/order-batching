import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

# -------------------------------------------------------
# PARÂMETROS
# -------------------------------------------------------
MAX_ITENS_POR_SUBONDA = 50
TABU_LIMIT = 200
LIMIAR = 3.0

# -------------------------------------------------------
# FUNÇÕES EXISTENTES (Tabu Approach)
# -------------------------------------------------------

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

    # Ordenar
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
    poss = encontrar_corredores_suficientes(sku_corredores, sku, qtd_needed)
    if not poss:
        return None

    candidatas = []
    area_atual = calcular_area_classe(uso_corredores_por_andar)
    for c in poss:
        andar_ = c['ANDAR']
        cor_   = c['CORREDOR']
        area_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar_, cor_)
        aumento = area_incluir - area_atual
        candidatas.append((c, aumento))

    candidatas.sort(key=lambda x: x[1])  # aumento asc

    melhor_cinfo, melhor_aumento = candidatas[0]
    if melhor_aumento <= LIMIAR:
        return melhor_cinfo
    else:
        # Tenta as próximas 'TABU_LIMIT'
        for i in range(1, min(TABU_LIMIT, len(candidatas))):
            cinfo_i, aumento_i = candidatas[i]
            if aumento_i < melhor_aumento * 1.2:
                return cinfo_i
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
    2) Se falhar => multi-corr com 'tabu'
    3) Se ainda faltar => fallback
    """
    df_ = df_caixas[df_caixas['CAIXA_ID'] == caixa_id]
    skus_pecas = df_.groupby('SKU')['PECAS'].sum().to_dict()

    # Single-corr
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
            for sku, qtd_ in skus_pecas.items():
                decrementa_estoque(sku_corredores, sku, a__, c__, qtd_)
            atualizar_area_classe(uso_corredores_por_andar, a__, c__)
            return [('single-corr', a__, c__, skus_pecas)]
        # else, segue multi-corr

    # Multi-corr (Tabu)
    alocacoes = []
    skus_restantes = {}
    for sku, qtd_ in skus_pecas.items():
        cinfo = escolher_corredor_tabu(sku, qtd_, uso_corredores_por_andar, sku_corredores)
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
    classes = {}
    for c_onda, group in caixas.groupby('CLASSE_ONDA'):
        classes[c_onda] = group.copy()
    return classes

# -------------------------------------------------------
# FUNÇÕES PARA FORMAR SUB-ONDAS
# -------------------------------------------------------

def estimar_corridor_caixa(df_caixa):
    """
    Exemplo simples:
    Pega o MIN e o MAX de corredor possível para cada SKU da caixa
    e faz a média.
    (Você pode inventar uma heurística mais refinada.)
    """
    min_corr = df_caixa['CORREDOR_MIN'].min()
    max_corr = df_caixa['CORREDOR_MAX'].max()
    if pd.isna(min_corr) or pd.isna(max_corr):
        # se não tiver nada
        return 0
    return (min_corr + max_corr)/2.0

def preparar_caixas_para_subondas(df_classe):
    """
    Cria colunas CORREDOR_MIN, CORREDOR_MAX para cada linha, depois agrupa por caixa.
    Exemplo: se a planilha 'caixas.csv' não tiver a info de CORREDOR_MIN e CORREDOR_MAX,
    precisamos gerá-la de alguma forma. Aqui está um placeholders.
    """
    # Dummmy: se seu CSV não tiver isso, inventamos algo (ex.: min=10, max=20).
    # Melhor: Precisaríamos de "dados" sobre os corredores possíveis. 
    # Mas aqui é só demonstrativo.
    
    df_classe = df_classe.copy()
    # Suponha que não temos colunas de corredor...
    # Vamos criar colunas fictícias:
    df_classe['CORREDOR_MIN'] = np.random.randint(1, 50, size=len(df_classe))
    df_classe['CORREDOR_MAX'] = df_classe['CORREDOR_MIN'] + np.random.randint(0, 30, size=len(df_classe))

    # Agora, criamos um DF com info de total_itens e corridor_est por caixa
    caixas_info = df_classe.groupby('CAIXA_ID').agg({
        'PECAS': 'sum',
        'CORREDOR_MIN': 'min',
        'CORREDOR_MAX': 'max'
    }).reset_index()

    # corridor_est = (min + max)/2
    caixas_info['corridor_est'] = (caixas_info['CORREDOR_MIN'] + caixas_info['CORREDOR_MAX'])/2.0

    return caixas_info

def formar_subondas_por_proximidade(caixas_info):
    """
    1) Ordena as caixas pelo corridor_est asc
    2) Agrupa até 6000 itens
    Retorna lista de subondas: [ { 'caixas_ids': [...], 'total_pecas': X }, ... ]
    """
    caixas_info = caixas_info.sort_values('corridor_est')
    subondas = []
    onda_atual = {'caixas_ids': [], 'total_pecas': 0}

    for _, row in caixas_info.iterrows():
        c_id = row['CAIXA_ID']
        t_pecas = row['PECAS']
        if onda_atual['total_pecas'] + t_pecas <= MAX_ITENS_POR_SUBONDA:
            # cabe na onda atual
            onda_atual['caixas_ids'].append(c_id)
            onda_atual['total_pecas'] += t_pecas
        else:
            # fecha a onda atual e abre outra
            subondas.append(onda_atual)
            onda_atual = {'caixas_ids': [c_id], 'total_pecas': t_pecas}
    # Final
    if onda_atual['caixas_ids']:
        subondas.append(onda_atual)

    return subondas

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
def main():
    caixas = pd.read_csv("data/caixas.csv")
    estoque = pd.read_csv("data/estoque.csv")

    # remover duplicatas
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()

    # Montar dicionário global, se quiser (pode ser que cada sub-onda crie sua cópia)
    sku_corredores_original = construir_sku_corredores_aninhado(estoque)

    # Organizar as caixas por classe
    caixas_por_classe = organizar_caixas_por_classe(caixas)

    # Dicionário final
    resultados = {}
    todas_areas = []  # para calcular média global se quiser

    for classe_onda, df_classe in caixas_por_classe.items():
        print(f"\n=== Classe {classe_onda} ===")

        # Passo 1: criar um "caixas_info" com corridor_est e total de pecas
        caixas_info = preparar_caixas_para_subondas(df_classe)

        # Passo 2: formar sub-ondas (lotes) com base na proximidade de corridor_est
        subondas = formar_subondas_por_proximidade(caixas_info)

        # Vamos processar cada sub-onda, gerando uma área
        areas_subonda = []

        # Precisamos do DataFrame original para cada sub-onda
        for idx_sub, subonda_info in enumerate(subondas, start=1):
            caixas_ids = subonda_info['caixas_ids']
            # Filtrar DF com essas caixas
            df_subonda = df_classe[df_classe['CAIXA_ID'].isin(caixas_ids)].copy()

            # Copiar o dicionário de estoque (se não quiser "competição" entre sub-ondas)
            sku_corredores_sub = {}
            # Copiamos a estrutura do original
            # Aqui, por simplicidade, vamos re-build do zero, mas se for grande, é custoso.
            sku_corredores_sub = construir_sku_corredores_aninhado(estoque)
            # (Se quiser a "competição" real de estoque, use a mesma 'sku_corredores_original'
            # e não recrie a cada sub-onda.)

            uso_corredores_por_andar = {}
            solucoes_subonda = {}

            # Processar cada caixa
            for caixa_id in tqdm(caixas_ids, desc=f"Processando sub-onda {idx_sub} da classe {classe_onda}"):
                sol = processar_caixa_tabu(caixa_id, df_subonda, sku_corredores_sub, uso_corredores_por_andar)
                solucoes_subonda[caixa_id] = sol

            area_sub = calcular_area_classe(uso_corredores_por_andar)
            areas_subonda.append(area_sub)

            print(f"  -> Sub-onda {idx_sub}: {len(caixas_ids)} caixas, total_pecas={subonda_info['total_pecas']}, area={area_sub:.2f}")

        # Ao final da classe, calculamos a média das sub-ondas
        if areas_subonda:
            media_classe = np.mean(areas_subonda)
        else:
            media_classe = 0
        resultados[classe_onda] = media_classe
        todas_areas.extend(areas_subonda)

        print(f"  ** Média de área das sub-ondas da classe {classe_onda} = {media_classe:.2f} **")

    # Se quiser, calcular a média global de todas as sub-ondas (todas as classes)
    if todas_areas:
        media_global = np.mean(todas_areas)
    else:
        media_global = 0
    print(f"\n=== MÉDIA GLOBAL DE TODAS AS SUB-ONDAS: {media_global:.2f} ===")
    print(f"=== RESULTADOS (Tabu Approach) ===")
    #Quantidade total de ondas
    print(f"Quantidade de ondas: {len(todas_areas)}")

if __name__ == "__main__":
    main()