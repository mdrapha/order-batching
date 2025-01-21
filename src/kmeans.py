# kmeans_approach.py

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import logging
from tqdm import tqdm

# Importando tudo do arquivo methods.py
from methods import (
    # Funções e variáveis que você precisa
    TABU_LIMIT,
    LIMIAR,
    calcular_area_classe,
    atualizar_area_classe,
    calcular_area_se_incluir,
    construir_sku_corredores_aninhado,
    decrementa_estoque,
    encontrar_corredores_suficientes,
    escolher_corredor_tabu,
    fallback_for_skus,
    processar_caixa_tabu,
    organizar_caixas_por_classe
)

logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

MAX_ITENS_POR_ONDA = 6000
K_ESTIMADO = 17

def preparar_caixas_para_cluster(df_classe):
    """
    Semelhante ao exemplo anterior, cria corridor_est fictício
    e retorna um DF com [CAIXA_ID, corridor_est, PECAS].
    """
    df_classe = df_classe.copy()
    # Se não tiver colunas CORREDOR_MIN / CORREDOR_MAX, criamos fictícias
    df_classe['CORREDOR_MIN'] = np.random.randint(1, 50, size=len(df_classe))
    df_classe['CORREDOR_MAX'] = df_classe['CORREDOR_MIN'] + np.random.randint(0, 30, size=len(df_classe))

    # Agrupar por caixa
    caixas_info = df_classe.groupby('CAIXA_ID').agg({
        'PECAS': 'sum',
        'CORREDOR_MIN': 'min',
        'CORREDOR_MAX': 'max'
    }).reset_index()
    caixas_info['corridor_est'] = (caixas_info['CORREDOR_MIN'] + caixas_info['CORREDOR_MAX'])/2.0
    return caixas_info

def subdividir_cluster_se_exceder(caixas_cluster, df_classe):
    """
    Se esse cluster exceder 6000 itens, dividimos em sub-lotes no 'caixas_cluster'.
    Retorna uma lista de sub-lotes, cada sub-lote = dict{'caixas_ids': [...], 'total_pecas': X}
    """
    subondas = []
    onda_atual = {'caixas_ids': [], 'total_pecas': 0}

    for idx, row in caixas_cluster.iterrows():
        cid = row['CAIXA_ID']
        t_pecas = row['PECAS']
        if onda_atual['total_pecas'] + t_pecas <= MAX_ITENS_POR_ONDA:
            onda_atual['caixas_ids'].append(cid)
            onda_atual['total_pecas'] += t_pecas
        else:
            subondas.append(onda_atual)
            onda_atual = {'caixas_ids': [cid], 'total_pecas': t_pecas}
    if onda_atual['caixas_ids']:
        subondas.append(onda_atual)
    return subondas

def main():
    caixas = pd.read_csv("data/caixas.csv")
    estoque = pd.read_csv("data/estoque.csv")

    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()

    sku_corredores_global = construir_sku_corredores_aninhado(estoque)
    caixas_por_classe = organizar_caixas_por_classe(caixas)

    todas_areas = []

    for classe_onda, df_classe in caixas_por_classe.items():
        print(f"\n=== Classe {classe_onda} ===")
        df_info = preparar_caixas_para_cluster(df_classe)
        if len(df_info) == 0:
            continue

        X = df_info[['corridor_est']].values
        k = min(len(X), K_ESTIMADO)
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X)
        df_info['cluster'] = kmeans.labels_

        # Agrupar por cluster, subdividir se > 6000
        subondas_clusters = []
        for c_label in sorted(df_info['cluster'].unique()):
            df_c = df_info[df_info['cluster'] == c_label].copy()
            soma_ = df_c['PECAS'].sum()
            if soma_ <= MAX_ITENS_POR_ONDA:
                subondas_clusters.append({
                    'caixas_ids': df_c['CAIXA_ID'].tolist(),
                    'total_pecas': soma_
                })
            else:
                # subdividir
                subs = subdividir_cluster_se_exceder(df_c, df_classe)
                subondas_clusters.extend(subs)

        # Processar sub-ondas
        areas_cls = []
        for sub_o in subondas_clusters:
            cids = sub_o['caixas_ids']
            df_sub = df_classe[df_classe['CAIXA_ID'].isin(cids)].copy()
            sku_sub = construir_sku_corredores_aninhado(estoque)
            uso_corr = {}
            for cid_ in tqdm(cids, desc=f"Process subonda cls={classe_onda}"):
                processar_caixa_tabu(cid_, df_sub, sku_sub, uso_corr)
            area_ = calcular_area_classe(uso_corr)
            areas_cls.append(area_)
            print(f"   Sub-onda cluster => {len(cids)} caixas, area={area_:.2f}, tot_pecas={sub_o['total_pecas']}")

        if areas_cls:
            media_cls = np.mean(areas_cls)
        else:
            media_cls = 0
        todas_areas.extend(areas_cls)
        print(f"   => Média sub-ondas classe {classe_onda} = {media_cls:.2f}")

    if todas_areas:
        media_global = np.mean(todas_areas)
    else:
        media_global = 0
    print(f"\nMédia global: {media_global:.2f}")
    print(f"Quantidade total de sub-ondas: {len(todas_areas)}")

if __name__ == "__main__":
    main()