# local_search_approach.py

import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

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

MAX_ITENS_POR_ONDA = 6000
MAX_ITER = 20

def calc_area_onda(df_onda, estoque_global):
    sku_corr_sub = construir_sku_corredores_aninhado(estoque_global)
    uso_corr = {}
    for cid in df_onda['CAIXA_ID'].unique():
        processar_caixa_tabu(cid, df_onda, sku_corr_sub, uso_corr)
    return calcular_area_classe(uso_corr)

def local_search_merge_split(subondas, df_classe, estoque_global):
    iteration = 0
    while iteration < MAX_ITER:
        iteration += 1
        print(f"\n-- Iteration {iteration}/{MAX_ITER} (Local Search) --")
        melhora = False

        # (1) Tentar merges
        sub_len = len(subondas)
        if sub_len > 1:
            print("   Tentando merges...")
            merged_bar = tqdm(total=(sub_len*(sub_len-1))//2, desc="   [Merges]", leave=False)

            i = 0
            while i < len(subondas):
                j = i + 1
                while j < len(subondas):
                    merged_bar.update(1)
                    pecas_i = subondas[i]['total_pecas']
                    pecas_j = subondas[j]['total_pecas']
                    if pecas_i + pecas_j <= MAX_ITENS_POR_ONDA:
                        area_i = subondas[i]['area']
                        area_j = subondas[j]['area']
                        cids_merged = subondas[i]['caixas_ids'] + subondas[j]['caixas_ids']

                        df_merged = df_classe[df_classe['CAIXA_ID'].isin(cids_merged)]
                        area_merged = calc_area_onda(df_merged, estoque_global)

                        # Exemplo: permitir até 10% de piora:
                        if area_merged < (1.1 * (area_i + area_j)):
                            new_onda = {
                                'caixas_ids': cids_merged,
                                'total_pecas': pecas_i + pecas_j,
                                'area': area_merged
                            }
                            subondas.pop(j)
                            subondas.pop(i)
                            subondas.append(new_onda)
                            melhora = True
                            merged_bar.close()
                            break
                    j += 1
                if melhora:
                    break
                i += 1

            merged_bar.close()
            if melhora:
                continue

        # (2) Tentar splits
        print("   Tentando splits...")
        splitted_bar = tqdm(total=len(subondas), desc="   [Splits]", leave=False)
        i = 0
        while i < len(subondas):
            splitted_bar.update(1)
            if subondas[i]['total_pecas'] > 3000:
                cids = subondas[i]['caixas_ids']
                if len(cids) > 1:
                    half = len(cids)//2
                    df1 = df_classe[df_classe['CAIXA_ID'].isin(cids[:half])]
                    df2 = df_classe[df_classe['CAIXA_ID'].isin(cids[half:])]
                    area1 = calc_area_onda(df1, estoque_global)
                    area2 = calc_area_onda(df2, estoque_global)
                    area_original = subondas[i]['area']
                    if (area1 + area2) < area_original:
                        new_onda1 = {
                            'caixas_ids': cids[:half],
                            'total_pecas': df1['PECAS'].sum(),
                            'area': area1
                        }
                        new_onda2 = {
                            'caixas_ids': cids[half:],
                            'total_pecas': df2['PECAS'].sum(),
                            'area': area2
                        }
                        subondas.pop(i)
                        subondas.append(new_onda1)
                        subondas.append(new_onda2)
                        melhora = True
                        splitted_bar.close()
                        break
            i += 1
        splitted_bar.close()

        if not melhora:
            print("   Nenhuma melhoria encontrada nesta iteração.")
            break

    return subondas

def main():
    caixas = pd.read_csv("data/caixas.csv")
    estoque = pd.read_csv("data/estoque.csv")
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()

    classes_dict = organizar_caixas_por_classe(caixas)

    todas_areas = []

    for classe_onda, df_classe in classes_dict.items():
        print(f"\n=== Classe {classe_onda} (Local Search) ===")

        # >>> MUDANÇA AQUI <<<
        # Em vez de criar subondas na ordem de CAIXA_ID, 
        # vamos ordenar as caixas por 'PECAS' desc, 
        # para resolver primeiro as caixas mais 'pesadas'.

        # 1) Ordenar as caixas de df_classe por PECAS desc
        caixas_ordenadas = (
            df_classe.groupby('CAIXA_ID')['PECAS'].sum()
            .reset_index()
            .sort_values('PECAS', ascending=False)
        )

        # 2) para cada caixa nessa ordem, criamos sub-onda isolada
        subondas = []
        for idx, row in tqdm(caixas_ordenadas.iterrows(), total=len(caixas_ordenadas),
                             desc="Criando sub-ondas iniciais (maior->menor)"):
            cid = row['CAIXA_ID']
            totalp = row['PECAS']
            df_caixa = df_classe[df_classe['CAIXA_ID'] == cid]
            area_ = calc_area_onda(df_caixa, estoque)
            subondas.append({
                'caixas_ids': [cid],
                'total_pecas': totalp,
                'area': area_
            })

        print(f"  Iniciamos com {len(subondas)} sub-ondas (uma por caixa, maior->menor).")

        # local search
        subondas = local_search_merge_split(subondas, df_classe, estoque)

        # resultado final
        areas_cls = [s['area'] for s in subondas]
        if areas_cls:
            media_cls = np.mean(areas_cls)
        else:
            media_cls = 0

        todas_areas.extend(areas_cls)
        print(f"  => Após local search, classe {classe_onda} tem {len(subondas)} sub-ondas. Média área={media_cls:.2f}")

    if todas_areas:
        media_global = np.mean(todas_areas)
    else:
        media_global = 0
    print(f"\nMédia global = {media_global:.2f}")
    print(f"Total de sub-ondas geradas: {len(todas_areas)}")
    print("Concluído (Local Search Approach) - Maior->Menor itens.")
    
if __name__ == "__main__":
    main()