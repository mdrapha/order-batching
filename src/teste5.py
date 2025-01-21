import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

# -------------------------------------------------------
# CONFIGURAÇÃO DE LOG
# -------------------------------------------------------
logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

# -------------------------------------------------------
# FUNÇÕES PARA CÁLCULO DE ÁREA
# -------------------------------------------------------

def calcular_area_classe(uso_corredores_por_andar):
    """
    Calcula a área total para uma dada classe de onda,
    com base no dicionário { andar: (menor_corredor, maior_corredor) }.
    
    Exemplo simples: area = c_max - c_min (por andar),
    e depois somamos para todos os andares.
    """
    area_total = 0
    for andar, (c_min, c_max) in uso_corredores_por_andar.items():
        # Exemplo básico: área = (c_max - c_min)
        area_andar = c_max - c_min
        area_total += area_andar
        # Se quiser penalizar mudança de andar ou usar pares/ímpares,
        # é só alterar este cálculo.
    return area_total


def atualizar_area_classe(uso_corredores_por_andar, andar, corredor):
    """
    Dado o dicionário {andar: (c_min, c_max)}, atualiza o par se necessário.
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
    Retorna a área caso (andar, corredor) seja incluído de forma temporária,
    sem alterar permanentemente `uso_corredores_por_andar`.
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


# -------------------------------------------------------
# FUNÇÕES PARA ESTRUTURA DE ESTOQUE (DICIONÁRIO ANINHADO)
# -------------------------------------------------------

def construir_sku_corredores_aninhado(estoque):
    """
    Cria um dicionário aninhado:
      sku_corredores[SKU][ANDAR] = [ { 'CORREDOR': X, 'PECAS': Y }, ... ]
    Ordenado em ordem decrescente de PECAS.
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
        
        sku_corredores[sku][andar].append({
            'CORREDOR': corredor,
            'PECAS': pecas
        })
    
    # Agora vamos ordenar cada lista por PECAS (desc), e em caso de empate, CORREDOR asc
    for sku in sku_corredores:
        for andar in sku_corredores[sku]:
            sku_corredores[sku][andar].sort(
                key=lambda x: (-x['PECAS'], x['CORREDOR'])
            )
    
    return sku_corredores


def decrementa_estoque(sku_corredores, sku, andar, corredor, qtd_retirada):
    """
    Atualiza o dicionário aninhado decrementando 'qtd_retirada'
    do corredor específico. Remove-o se PECAS cair para 0 (ou < 0).
    Mantém a ordem decrescente de PECAS (pode ser que precise reordenar, 
    mas geralmente só cai, então a posição deve permanecer ou ir para o final).
    """
    if sku not in sku_corredores:
        return
    
    if andar not in sku_corredores[sku]:
        return
    
    corredores_list = sku_corredores[sku][andar]
    for i, info in enumerate(corredores_list):
        if info['CORREDOR'] == corredor:
            info['PECAS'] -= qtd_retirada
            if info['PECAS'] <= 0:
                # Remove esse corredor
                corredores_list.pop(i)
            else:
                # Como 'PECAS' diminuiu, se precisar reordenar, faz aqui:
                # Nesse caso, normalmente ele só iria para baixo na lista.
                # Podemos reposicioná-lo de maneira simples:
                # (Mas vamos deixar sem recolocar, pois isso pode ter pouco impacto.)
                pass
            break
    
    # Se esvaziou a lista, pode remover esse 'andar'
    if len(corredores_list) == 0:
        sku_corredores[sku].pop(andar, None)


# -------------------------------------------------------
# FUNÇÕES DE BUSCA DE CORREDORES
# -------------------------------------------------------

def encontrar_corredores_suficientes(sku_corredores, sku, qtd_necessaria):
    """
    Percorre todas as listas (andar -> corredores) desse SKU e
    retorna uma lista de dicionários:
      [ { 'ANDAR': A, 'CORREDOR': X, 'PECAS': P }, ... ]
    onde P >= qtd_necessaria.
    
    Cada sub-lista já está em ordem desc de PECAS,
    então podemos interromper cedo se P < qtd_necessaria.
    
    Como precisamos devolver 'ANDAR' junto, 
    faremos um flatten com a informação do andar.
    """
    if sku not in sku_corredores:
        return []
    
    result = []
    # Podemos iterar em todos os andares
    # (ou escolher uma ordem de andares se fizer sentido).
    for andar, lista_corredores in sku_corredores[sku].items():
        # lista_corredores já está ordenada
        for info in lista_corredores:
            if info['PECAS'] < qtd_necessaria:
                # como está ordenado em desc, 
                # não há mais o que ver nesse andar
                break
            # se chegou aqui, info['PECAS'] >= qtd_necessaria
            result.append({
                'ANDAR': andar,
                'CORREDOR': info['CORREDOR'],
                'PECAS': info['PECAS']
            })
    return result


def encontrar_corredores_no_andar(sku_corredores, sku, andar, qtd_necessaria):
    """
    Versão otimizada para multi-corridor: 
    busca corredores suficientes somente em um andar específico,
    retornando lista de { 'CORREDOR', 'PECAS' } (sem 'ANDAR', pois já sabemos).
    """
    if sku not in sku_corredores:
        return []
    if andar not in sku_corredores[sku]:
        return []
    
    lista_corredores = sku_corredores[sku][andar]
    # Essa lista está ordenada em desc por PECAS
    corredores_suficientes = []
    for info in lista_corredores:
        if info['PECAS'] < qtd_necessaria:
            break
        corredores_suficientes.append(info)
    
    return corredores_suficientes


# -------------------------------------------------------
# ORGANIZAR CAIXAS POR CLASSE
# -------------------------------------------------------

def organizar_caixas_por_classe(caixas):
    """
    Retorna um dicionário { classe_onda: DataFrame com as caixas dessa classe }.
    """
    classes = {}
    for classe_onda, group in caixas.groupby('CLASSE_ONDA'):
        classes[classe_onda] = group.copy()
    return classes


# -------------------------------------------------------
# PROCESSAR UMA CLASSE DE ONDA
# -------------------------------------------------------

def processar_classe_onda(caixas_classe, sku_corredores):
    """
    Processa as caixas de uma classe de onda específica, 
    criando soluções single-corridor e multi-corridor
    e minimizando a área total (conforme a heurística).

    Retorna:
      solucoes_por_caixa: dict { caixa_id: ... ou None se não atendida }
      area_final: valor float com a área total.
    """
    solucoes_por_caixa = {}
    uso_corredores_por_andar = {}  # armazena (c_min, c_max) por andar
    
    caixa_ids = caixas_classe['CAIXA_ID'].unique()
    
    # Vamos separar quais caixas podem ser single-corridor
    single_corridor_caixas = []
    multi_corridor_caixas = []
    
    for caixa_id in caixa_ids:
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()
        
        # Checar se há 1 corredor que supra todos os SKUs
        # Precisamos ver a interseção de corredores_suficientes
        sets_corredores = []
        for sku, qtd in skus_pecas.items():
            lista_cands = encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            # converter em set de (andar, corredor)
            s = set((c['ANDAR'], c['CORREDOR']) for c in lista_cands)
            sets_corredores.append(s)
        
        if sets_corredores:
            corredores_comuns = set.intersection(*sets_corredores)
        else:
            corredores_comuns = set()
        
        if corredores_comuns:
            single_corridor_caixas.append(caixa_id)
        else:
            multi_corridor_caixas.append(caixa_id)
    
    # -------------------------------------------------------
    # A) SINGLE-CORRIDOR
    # -------------------------------------------------------
    for caixa_id in tqdm(single_corridor_caixas, desc="Processando caixas Single-Corridor"):
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()
        
        # Novamente, achar a interseção de corredores
        sets_corredores = []
        for sku, qtd in skus_pecas.items():
            lista_cands = encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            s = set((c['ANDAR'], c['CORREDOR']) for c in lista_cands)
            sets_corredores.append(s)
        
        corredores_comuns = set.intersection(*sets_corredores) if sets_corredores else set()
        
        if not corredores_comuns:
            logging.error(f"Single-corridor falhou para caixa {caixa_id}")
            solucoes_por_caixa[caixa_id] = None
            continue
        
        # Escolher o corredor que minimiza aumento de área
        melhor_corredor = None
        melhor_aumento = float('inf')
        
        for (andar, corredor) in corredores_comuns:
            area_atual = calcular_area_classe(uso_corredores_por_andar)
            area_se_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar, corredor)
            aumento = area_se_incluir - area_atual
            if aumento < melhor_aumento:
                melhor_aumento = aumento
                melhor_corredor = (andar, corredor)
        
        if melhor_corredor is None:
            solucoes_por_caixa[caixa_id] = None
            continue
        
        # Se temos um corredor, atualiza área e decrementa estoque
        andar_sol, corredor_sol = melhor_corredor
        atualizar_area_classe(uso_corredores_por_andar, andar_sol, corredor_sol)
        
        # Decrementa o estoque para cada SKU da caixa
        for sku, qtd_req in skus_pecas.items():
            decrementa_estoque(sku_corredores, sku, andar_sol, corredor_sol, qtd_req)
        
        solucoes_por_caixa[caixa_id] = {'andar_corredor': melhor_corredor}
    
    # -------------------------------------------------------
    # B) MULTI-CORRIDOR
    # -------------------------------------------------------
    for caixa_id in tqdm(multi_corridor_caixas, desc="Processando caixas Multi-Corridor"):
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()
        
        skus_restantes = dict(skus_pecas)
        corredores_usados = []
        
        # 1) Calcular densidade de cada andar (pecas / área) no dicionário
        #    Precisamos somar 'PECAS' em cada andar para todos SKUs,
        #    mas como a estrutura é aninhada, podemos apenas extrair uma
        #    estimativa rápida: soma total de PECAS em cada ANDAR para todos SKUs no dicionário.
        
        # Montar (andar -> (min_corr, max_corr, total_pecas))
        andar_info = {}
        for sku in sku_corredores:
            for andar_ in sku_corredores[sku]:
                # Soma a PECAS de todos os corredores naquele andar
                for corinfo in sku_corredores[sku][andar_]:
                    pecas_ = corinfo['PECAS']
                    corr_ = corinfo['CORREDOR']
                    
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
            area_andar = (cmax - cmin) + 1  # +1 se achar relevante
            total_p = andar_info[andar_]['total_pecas']
            densidade = total_p / area_andar if area_andar else 0
            densidade_por_andar.append((andar_, densidade))
        
        # Ordenar andares por densidade desc
        densidade_por_andar.sort(key=lambda x: x[1], reverse=True)
        
        # Tentar atender SKUs nesse ranking de andares
        for (andar_, dens_) in densidade_por_andar:
            if not skus_restantes:
                break  # tudo atendido
            
            skus_atendidos = []
            for sku, qtd_req in list(skus_restantes.items()):
                # Buscamos corredores no andar_ com >= qtd_req
                cands = encontrar_corredores_no_andar(sku_corredores, sku, andar_, qtd_req)
                if not cands:
                    continue  # sem corredor suficiente
                
                # Escolher o corredor que minimize aumento de área
                melhor_corr = None
                melhor_aumento = float('inf')
                
                for corinfo in cands:
                    corr = corinfo['CORREDOR']
                    area_atual = calcular_area_classe(uso_corredores_por_andar)
                    area_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar_, corr)
                    aumento = area_incluir - area_atual
                    if aumento < melhor_aumento:
                        melhor_aumento = aumento
                        melhor_corr = corinfo
                
                if melhor_corr:
                    # Atualizar a área
                    atualizar_area_classe(uso_corredores_por_andar, andar_, melhor_corr['CORREDOR'])
                    # Decrementar o estoque
                    decrementa_estoque(sku_corredores, sku, andar_, melhor_corr['CORREDOR'], qtd_req)
                    
                    # Registrar
                    corredores_usados.append((andar_, melhor_corr['CORREDOR'], sku, qtd_req))
                    skus_atendidos.append(sku)
            
            for sku_ in skus_atendidos:
                skus_restantes.pop(sku_, None)
        
        if skus_restantes:
            logging.error(f"Caixa {caixa_id} NÃO foi totalmente atendida (multi-corridor).")
            solucoes_por_caixa[caixa_id] = None
        else:
            solucoes_por_caixa[caixa_id] = corredores_usados
    
    # Por fim, calculamos a área total
    area_final = calcular_area_classe(uso_corredores_por_andar)
    return solucoes_por_caixa, area_final


# -------------------------------------------------------
# FLUXO PRINCIPAL
# -------------------------------------------------------

def main():
    # 1) Carregar dados das caixas e do estoque
    caixas = pd.read_csv("data/caixas.csv")  # colunas: CAIXA_ID, SKU, CLASSE_ONDA, PECAS
    estoque = pd.read_csv("data/estoque.csv")  # colunas: ANDAR, CORREDOR, SKU, PECAS
    
    # 2) Remover duplicatas
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()
    
    # 3) Construir estrutura aninhada {SKU: {ANDAR: [ {CORREDOR, PECAS}, ... ] } }
    sku_corredores = construir_sku_corredores_aninhado(estoque)
    
    # 4) Separar as caixas por classe de onda
    caixas_por_classe = organizar_caixas_por_classe(caixas)
    
    # 5) Processar cada classe
    resultados = {}
    for classe_onda, caixas_classe in caixas_por_classe.items():
        print(f"\nProcessando classe de onda: {classe_onda}")
        solucoes_classe, area_final = processar_classe_onda(caixas_classe, sku_corredores)
        resultados[classe_onda] = {
            'solucoes': solucoes_classe,
            'area_final': area_final
        }
    
    # 6) Exibir resultados
    print("\nRESULTADOS FINAIS:")
    for classe_onda, info in resultados.items():
        print(f"Classe {classe_onda}: área final = {info['area_final']:.2f}")
        for caixa_id, solucao in info['solucoes'].items():
            if solucao is None:
                print(f"  Caixa {caixa_id} => NÃO ATENDIDA")
            else:
                print(f"  Caixa {caixa_id} => Solução: {solucao}")
    
    print("\nProcessamento concluído.")


if __name__ == "__main__":
    main()