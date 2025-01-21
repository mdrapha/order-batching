import pandas as pd
import numpy as np
import itertools
from collections import defaultdict
import logging
from tqdm import tqdm

# -------------------------------------------------------
# CONFIGURAÇÃO DE LOG
# -------------------------------------------------------
logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

# -------------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------------

def calcular_area_classe(uso_corredores_por_andar):
    """
    Calcula a área total para uma dada classe de onda, 
    com base no dicionário { andar: (menor_corredor, maior_corredor) }.
    
    Exemplo simples de cálculo de área: area = (c_max - c_min).
    Ajuste de acordo com sua regra de par/ímpar ou penalidade de andar.
    """
    area_total = 0
    for andar, (c_min, c_max) in uso_corredores_por_andar.items():
        # Exemplo simplificado: área = (c_max - c_min)
        area_andar = c_max - c_min
        area_total += area_andar
        # Se quiser penalizar mudança de andar, inclua aqui

    return area_total


def atualizar_area_classe(uso_corredores_por_andar, andar, corredor):
    """
    Atualiza o dicionário que rastreia o menor e maior corredor usados em cada andar.
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
    Retorna a área total caso inclua (andar, corredor) temporariamente,
    sem alterar permanentemente o dicionário uso_corredores_por_andar.
    """
    temp_uso = dict(uso_corredores_por_andar)  # cópia rasa
    if andar not in temp_uso:
        temp_uso[andar] = (corredor, corredor)
    else:
        c_min, c_max = temp_uso[andar]
        c_min = min(c_min, corredor)
        c_max = max(c_max, corredor)
        temp_uso[andar] = (c_min, c_max)
    
    return calcular_area_classe(temp_uso)


def encontrar_corredores_suficientes(sku_corredores, sku, qtd_necessaria):
    """
    Retorna a lista de corredores (dicionários) onde o SKU está disponível 
    em quantidade >= qtd_necessaria.
    
    Como 'sku_corredores[sku]' já está ordenado por PECAS desc,
    interrompemos a busca assim que c['PECAS'] < qtd_necessaria.
    """
    if sku not in sku_corredores:
        return []
    
    corredores = sku_corredores[sku]
    corredores_suficientes = []
    
    for c in corredores:
        if c['PECAS'] < qtd_necessaria:
            # Como está em ordem desc por PECAS,
            # nenhum corredor seguinte terá PECAS >= qtd_necessaria.
            break
        corredores_suficientes.append(c)
    
    return corredores_suficientes


def update_sku_corredores(estoque):
    """
    Constrói/atualiza o dicionário {SKU: [ {ANDAR, CORREDOR, PECAS}, ... ]}, 
    ordenando cada lista por: 
      - PECAS desc
      - CORREDOR asc
      - ANDAR asc (exemplo)
    """
    sku_corredores = {}
    for sku, group in estoque.groupby('SKU'):
        registros = group[['ANDAR', 'CORREDOR', 'PECAS']].to_dict('records')
        # Ordenar: PECAS desc, depois CORREDOR asc, depois ANDAR asc
        registros.sort(key=lambda x: (-x['PECAS'], x['CORREDOR'], x['ANDAR']))
        sku_corredores[sku] = registros
    return sku_corredores


# -------------------------------------------------------
# PRÉ-PROCESSAR AS CAIXAS (OPCIONAL)
# -------------------------------------------------------

def preprocess_caixas(caixas):
    """
    Exemplo: ordena as caixas de acordo com a quantidade total de peças,
    de maior para menor, para potencialmente resolver primeiro as caixas 'grandes'.
    """
    caixas = caixas.copy()
    # Calcular total de peças por caixa
    caixas['TOTAL_PECAS_CAIXA'] = caixas.groupby('CAIXA_ID')['PECAS'].transform('sum')
    # Ordenar do maior para o menor
    caixas = caixas.sort_values(by='TOTAL_PECAS_CAIXA', ascending=False)
    return caixas


# -------------------------------------------------------
# PASSO 1: ORGANIZAR AS CAIXAS EM CLASSES
# -------------------------------------------------------

def organizar_caixas_por_classe(caixas):
    """
    Retorna um dicionário {classe_onda: DataFrame com as caixas dessa classe}.
    """
    classes = {}
    for classe_onda, group in caixas.groupby('CLASSE_ONDA'):
        classes[classe_onda] = group.copy()
    return classes


# -------------------------------------------------------
# PASSO 2: PROCESSAR CAIXAS DE UMA MESMA CLASSE
# -------------------------------------------------------

def processar_classe_onda(caixas_classe, estoque, sku_corredores):
    """
    Processa as caixas de uma classe de onda específica, minimizando a área total.
    
    1) Prioriza as caixas que podem ser resolvidas em um ÚNICO corredor (single-corridor).
    2) Em seguida, trata as caixas que exigem múltiplos corredores (multi-corridor):
       - Tenta atender primeiro no andar com maior 'densidade' (pecas / área).
       - Escolhe os corredores que minimizam o aumento de área.
    3) Atualiza o estoque e guarda a solução (ou None se não atendida).
    """
    
    # Dicionário para armazenar soluções por caixa
    solucoes_por_caixa = {}
    
    # Dicionário que rastreia (c_min, c_max) por andar
    uso_corredores_por_andar = {}
    
    # Identificar caixas "single-corridor" vs "multi-corridor"
    caixa_ids = caixas_classe['CAIXA_ID'].unique()
    single_corridor_caixas = []
    multi_corridor_caixas = []
    
    for caixa_id in caixa_ids:
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()
        
        # Verificar se há algum corredor que supra todos os SKUs de uma só vez
        corredores_possiveis_por_sku = {
            sku: encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            for sku, qtd in skus_pecas.items()
        }
        
        lista_sets = []
        for sku, qtd in skus_pecas.items():
            corredores_suf = corredores_possiveis_por_sku[sku]
            set_corr = set((c['ANDAR'], c['CORREDOR']) for c in corredores_suf)
            lista_sets.append(set_corr)
        
        # Interseção de (andar, corredor) que atende TODOS os SKUs
        if lista_sets:
            corredores_comuns = set.intersection(*lista_sets)
        else:
            corredores_comuns = set()
        
        # Se existe pelo menos 1 corredor que atenda todos os SKUs, é single-corridor
        if len(corredores_comuns) > 0:
            single_corridor_caixas.append(caixa_id)
        else:
            multi_corridor_caixas.append(caixa_id)

    # -------------------------------------------------------
    # A) Resolver Caixas "Single-Corridor"
    # -------------------------------------------------------
    # Para acompanhar o progresso das caixas single-corridor
    for caixa_id in tqdm(single_corridor_caixas, desc="Processando caixas Single-Corridor"):
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()
        
        corredores_possiveis_por_sku = {
            sku: encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            for sku, qtd in skus_pecas.items()
        }
        
        lista_sets = []
        for sku, qtd in skus_pecas.items():
            corredores_suf = corredores_possiveis_por_sku[sku]
            set_corr = set((c['ANDAR'], c['CORREDOR']) for c in corredores_suf)
            lista_sets.append(set_corr)
        
        corredores_comuns = set.intersection(*lista_sets)
        
        if not corredores_comuns:
            logging.error(f"Não foi possível encontrar corredor único para caixa {caixa_id}")
            solucoes_por_caixa[caixa_id] = None
            continue
        
        # Escolher o corredor que minimiza aumento de área
        melhor_corredor = None
        melhor_aumento_area = float('inf')
        
        for (andar, corredor) in corredores_comuns:
            area_atual = calcular_area_classe(uso_corredores_por_andar)
            area_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar, corredor)
            aumento = area_incluir - area_atual
            
            if aumento < melhor_aumento_area:
                melhor_aumento_area = aumento
                melhor_corredor = (andar, corredor)
        
        if melhor_corredor:
            andar, corredor = melhor_corredor
            # Atualizar área (registro de menor e maior corredor)
            atualizar_area_classe(uso_corredores_por_andar, andar, corredor)
            # Abater do estoque
            for sku, qtd_req in skus_pecas.items():
                idx_estoque = estoque[
                    (estoque['ANDAR'] == andar) &
                    (estoque['CORREDOR'] == corredor) &
                    (estoque['SKU'] == sku)
                ].index
                if not idx_estoque.empty:
                    estoque.loc[idx_estoque, 'PECAS'] -= qtd_req
                    # Remover se zerado
                    estoque = estoque[estoque['PECAS'] > 0]
            
            # Atualizar sku_corredores para próximos passos
            sku_corredores = update_sku_corredores(estoque)
            solucoes_por_caixa[caixa_id] = {'andar_corredor': melhor_corredor}
        else:
            solucoes_por_caixa[caixa_id] = None

    # -------------------------------------------------------
    # B) Resolver Caixas "Multi-Corridor"
    # -------------------------------------------------------
    # Para acompanhar o progresso das caixas multi-corridor
    for caixa_id in tqdm(multi_corridor_caixas, desc="Processando caixas Multi-Corridor"):
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()
        
        # Precisamos atender cada SKU. Vamos iterar pelos andares de maior "densidade".
        # 1) Calcular densidade (pecas / área) de cada andar
        andar_info = {}
        for sku, corredores in sku_corredores.items():
            for c in corredores:
                andar_ = c['ANDAR']
                corr_ = c['CORREDOR']
                pecas_ = c['PECAS']
                
                if andar_ not in andar_info:
                    andar_info[andar_] = {
                        'corr_min': corr_,
                        'corr_max': corr_,
                        'total_pecas': pecas_
                    }
                else:
                    andar_info[andar_]['corr_min'] = min(andar_info[andar_]['corr_min'], corr_)
                    andar_info[andar_]['corr_max'] = max(andar_info[andar_]['corr_max'], corr_)
                    andar_info[andar_]['total_pecas'] += pecas_
        
        densidade_por_andar = []
        for andar_ in andar_info:
            cmin = andar_info[andar_]['corr_min']
            cmax = andar_info[andar_]['corr_max']
            area_andar = cmax - cmin + 1  # simplificado
            total_pecas = andar_info[andar_]['total_pecas']
            
            densidade = total_pecas / area_andar if area_andar else 0
            densidade_por_andar.append((andar_, densidade))
        
        # Ordenar do andar mais denso para o menos denso
        densidade_por_andar.sort(key=lambda x: x[1], reverse=True)
        
        skus_restantes = dict(skus_pecas)
        corredores_utilizados = []
        
        # Tentar atender no andar de maior densidade primeiro
        for (andar_, dens_) in densidade_por_andar:
            if not skus_restantes:
                break  # Todos SKUs atendidos
            
            skus_atendidos = []
            for sku, qtd_req in list(skus_restantes.items()):
                # Corredores nesse andar com estoque >= qtd_req
                corredores_no_andar = []
                
                # Aqui podemos aproveitar que 'sku_corredores[sku]' 
                # já vem ordenado por PECAS desc
                if sku in sku_corredores:
                    for cinfo in sku_corredores[sku]:
                        if cinfo['ANDAR'] == andar_ and cinfo['PECAS'] >= qtd_req:
                            corredores_no_andar.append(cinfo)
                        # Se cinfo['PECAS'] < qtd_req e lista está em desc,
                        # então nenhum próximo corredor servirá, mas 
                        # precisamos verificar se a troca de ANDAR também é necessária etc.
                
                if corredores_no_andar:
                    melhor_corr = None
                    melhor_aumento_area = float('inf')
                    
                    for cinfo in corredores_no_andar:
                        corr = cinfo['CORREDOR']
                        area_atual = calcular_area_classe(uso_corredores_por_andar)
                        area_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar_, corr)
                        aumento = area_incluir - area_atual
                        
                        if aumento < melhor_aumento_area:
                            melhor_aumento_area = aumento
                            melhor_corr = cinfo
                    
                    if melhor_corr:
                        # Atualizar área
                        atualizar_area_classe(uso_corredores_por_andar, andar_, melhor_corr['CORREDOR'])
                        # Abater estoque
                        idx_estoque = estoque[
                            (estoque['ANDAR'] == andar_) &
                            (estoque['CORREDOR'] == melhor_corr['CORREDOR']) &
                            (estoque['SKU'] == sku)
                        ].index
                        
                        if not idx_estoque.empty:
                            estoque.loc[idx_estoque, 'PECAS'] -= qtd_req
                            estoque = estoque[estoque['PECAS'] > 0]
                        
                        # Atualizar dicionário de corredores
                        sku_corredores = update_sku_corredores(estoque)
                        
                        # Registrar
                        corredores_utilizados.append((andar_, melhor_corr['CORREDOR'], sku, qtd_req))
                        skus_atendidos.append(sku)
            
            # Remover SKUs já atendidos
            for sku_ in skus_atendidos:
                skus_restantes.pop(sku_, None)
        
        if skus_restantes:
            logging.error(f"Caixa {caixa_id} não pôde ser totalmente atendida (multi-corridor).")
            solucoes_por_caixa[caixa_id] = None
        else:
            solucoes_por_caixa[caixa_id] = corredores_utilizados
    
    # Área final usada pela classe
    area_final = calcular_area_classe(uso_corredores_por_andar)
    
    return solucoes_por_caixa, area_final


# -------------------------------------------------------
# FLUXO PRINCIPAL
# -------------------------------------------------------

def main():
    # Carregar dados das caixas e do estoque
    caixas = pd.read_csv("data/caixas.csv")  # colunas: CAIXA_ID, SKU, CLASSE_ONDA, PECAS, ...
    estoque = pd.read_csv("data/estoque.csv")  # colunas: ANDAR, CORREDOR, SKU, PECAS, ...
    
    # Remover duplicatas, se houver
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()
    
    # (Opcional) Ordenar as caixas de maior para menor quantidade total:
    caixas = preprocess_caixas(caixas)

    # Montar dicionário {SKU: [ {ANDAR, CORREDOR, PECAS}, ... ]}, ordenado
    sku_corredores = update_sku_corredores(estoque)
    
    # Agrupar as caixas por classe de onda
    caixas_por_classe = organizar_caixas_por_classe(caixas)
    
    # Processar cada classe
    resultados = {}
    for classe_onda, caixas_classe in caixas_por_classe.items():
        print(f"\nProcessando classe de onda: {classe_onda}")
        
        # Processar as caixas dessa classe
        solucoes_classe, area_final = processar_classe_onda(caixas_classe, estoque, sku_corredores)
        
        resultados[classe_onda] = {
            'solucoes': solucoes_classe,
            'area_final': area_final
        }
    
    # Exibir resultados finais
    print("\nRESULTADOS FINAIS:")
    for classe_onda, info in resultados.items():
        print(f"Classe {classe_onda}: área final = {info['area_final']:.2f}")
        for caixa_id, solucao in info['solucoes'].items():
            if solucao is None:
                print(f"  Caixa {caixa_id} => NÃO ATENDIDA (estoque insuficiente ou falha).")
            else:
                print(f"  Caixa {caixa_id} => Corredores usados: {solucao}")

    print("\nProcessamento concluído.")

if __name__ == "__main__":
    main()