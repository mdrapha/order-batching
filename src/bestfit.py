# bestfit_approach.py

import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

# Importando tudo do nosso methods.py
from methods import (
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

MAX_ITENS_POR_ONDA = 1000  # não force encher até 6000, mas não ultrapassar

def preparar_caixas_para_bestfit(df_classe):
    df_classe = df_classe.copy()
    # gerar corridor_est fictício
    df_classe['CORREDOR_MIN'] = np.random.randint(1, 50, size=len(df_classe))
    df_classe['CORREDOR_MAX'] = df_classe['CORREDOR_MIN'] + np.random.randint(0, 30, size=len(df_classe))

    caixas_info = df_classe.groupby('CAIXA_ID').agg({
        'PECAS': 'sum',
        'CORREDOR_MIN': 'min',
        'CORREDOR_MAX': 'max'
    }).reset_index()
    caixas_info['corridor_est'] = (caixas_info['CORREDOR_MIN'] + caixas_info['CORREDOR_MAX']) / 2.0
    return caixas_info

def best_fit_decreasing_subondas(caixas_info):
    """
    Exemplo: Ordenar as caixas por 'PECAS' desc
    e tentamos encaixar na onda existente que tenha corridor_est_medio
    mais próximo do corridor_est da caixa, sem passar 6000 itens.
    """
    caixas_info = caixas_info.sort_values('PECAS', ascending=False).reset_index(drop=True)
    subondas = []

    for _, row in caixas_info.iterrows():
        c_id = row['CAIXA_ID']
        t_pecas = row['PECAS']
        c_est   = row['corridor_est']

        melhor_onda = None
        melhor_dist = float('inf')
        for i, onda in enumerate(subondas):
            if onda['total_pecas'] + t_pecas <= MAX_ITENS_POR_ONDA:
                dist_ = abs(onda['corridor_est_medio'] - c_est)
                if dist_ < melhor_dist:
                    melhor_dist = dist_
                    melhor_onda = i
        # se não coube ou ficou ruim
        if melhor_onda is None:
            # cria nova onda
            subondas.append({
                'caixas_ids': [c_id],
                'total_pecas': t_pecas,
                'corridor_est_medio': c_est
            })
        else:
            # encaixar na onda
            subondas[melhor_onda]['caixas_ids'].append(c_id)
            subondas[melhor_onda]['total_pecas'] += t_pecas
            n_caixas = len(subondas[melhor_onda]['caixas_ids'])
            old_est  = subondas[melhor_onda]['corridor_est_medio']
            # recalcular a média
            new_est = (old_est*(n_caixas-1) + c_est)/n_caixas
            subondas[melhor_onda]['corridor_est_medio'] = new_est

    return subondas

def main():
    caixas = pd.read_csv("data/caixas.csv")
    estoque = pd.read_csv("data/estoque.csv")
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()

    sku_corr_original = construir_sku_corredores_aninhado(estoque)
    classes_dict = organizar_caixas_por_classe(caixas)

    todas_areas = []

    for classe_onda, df_classe in classes_dict.items():
        print(f"\n=== Classe {classe_onda} (Best Fit) ===")

        df_info = preparar_caixas_para_bestfit(df_classe)
        subondas = best_fit_decreasing_subondas(df_info)

        areas_classe = []
        for idx_sub, sonda in enumerate(subondas, start=1):
            c_ids = sonda['caixas_ids']
            df_sub = df_classe[df_classe['CAIXA_ID'].isin(c_ids)].copy()
            sku_sub = construir_sku_corredores_aninhado(estoque)
            uso_corr = {}
            for cid_ in tqdm(c_ids, desc=f"Classe {classe_onda} - Onda {idx_sub}"):
                processar_caixa_tabu(cid_, df_sub, sku_sub, uso_corr)

            area_ = calcular_area_classe(uso_corr)
            areas_classe.append(area_)
            print(f"   Sub-onda {idx_sub}: {len(c_ids)} caixas, total={sonda['total_pecas']}, area={area_:.2f}")

        if areas_classe:
            media_cls = np.mean(areas_classe)
        else:
            media_cls = 0
        todas_areas.extend(areas_classe)
        print(f"   => Média sub-ondas classe {classe_onda} = {media_cls:.2f}")

    if todas_areas:
        media_global = np.mean(todas_areas)
    else:
        media_global = 0
    print(f"\nMédia global (Best Fit) = {media_global:.2f}")
    print(f"Total de sub-ondas: {len(todas_areas)}")
    print("Concluído (Best Fit Approach).")

if __name__ == "__main__":
    main()