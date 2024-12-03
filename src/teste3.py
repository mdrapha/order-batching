import pandas as pd
import numpy as np
import itertools
from collections import defaultdict
import logging
from tqdm import tqdm
import time
import yaml
import csv

# Configurar logging
logging.basicConfig(filename='erros.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(message)s')

# Função para calcular a distância entre corredores
def calculate_distance(corredores):
    corredores_ordenados = sorted(corredores, key=lambda x: (x['ANDAR'], x['CORREDOR']))
    total_distance = 0
    for i in range(len(corredores_ordenados) - 1):
        c1 = corredores_ordenados[i]
        c2 = corredores_ordenados[i+1]
        dist = abs(int(c1['CORREDOR']) - int(c2['CORREDOR']))
        if c1['ANDAR'] != c2['ANDAR']:
            dist += 10  # Penalidade para mudança de andar
        total_distance += dist
    return total_distance

def generate_combinations(sku_list, sku_corredores, top_corredores_limit, max_combinations):
    corredores_por_sku = []
    for sku in sku_list:
        corredores = sku_corredores.get(sku, [])
        if not corredores:
            logging.error(f"SKU {sku} não está disponível em nenhum corredor.")
            return []
        # Ajustar o número de corredores considerados dinamicamente
        if len(sku_list) <= 5:
            # Para caixas com poucos SKUs, considerar todos os corredores
            top_corredores = corredores  # Considerar todos os corredores
        else:
            top_corredores = corredores[:top_corredores_limit]  # Considerar os N melhores corredores
        corredores_por_sku.append(top_corredores)
    # Gerar combinações limitadas usando iteradores
    combinations = itertools.islice(itertools.product(*corredores_por_sku), max_combinations)
    combinations = list(combinations)  # Converter para lista para medir o tempo
    return combinations

def generate_greedy_solution(sku_list, sku_corredores):
    solution = []
    for sku in sku_list:
        corredores = sku_corredores.get(sku, [])
        if not corredores:
            logging.error(f"SKU {sku} não está disponível em nenhum corredor.")
            return None
        # Selecionar o melhor corredor (mais peças e andar mais baixo)
        corredores.sort(key=lambda x: (-x['PECAS'], x['ANDAR']))
        best_corredor = corredores[0]
        solution.append(best_corredor)
    return solution

def update_sku_corredores(estoque):
    # Use dict comprehension to build the dictionary efficiently
    sku_corredores = {sku: group[['ANDAR', 'CORREDOR', 'PECAS']].to_dict('records') for sku, group in estoque.groupby('SKU')}
    return sku_corredores

def verificar_estoque_suficiente(caixas, estoque):
    caixas_nao_atendidas = []
    caixas_ids = caixas['CAIXA_ID'].unique()
    estoque_disponivel = estoque.groupby('SKU')['PECAS'].sum()
    for caixa_id in caixas_ids:
        caixa_skus = caixas[caixas['CAIXA_ID'] == caixa_id][['SKU', 'PECAS']]
        pecas_necessarias = caixa_skus.groupby('SKU')['PECAS'].sum()
        estoque_suficiente = True
        for sku, qtd_necessaria in pecas_necessarias.items():
            qtd_disponivel = estoque_disponivel.get(sku, 0)
            if qtd_necessaria > qtd_disponivel:
                estoque_suficiente = False
                logging.error(f"Estoque insuficiente para SKU {sku} na caixa {caixa_id}. Necessário: {qtd_necessaria}, Disponível: {qtd_disponivel}")
                break
        if not estoque_suficiente:
            caixas_nao_atendidas.append(caixa_id)
    return caixas_nao_atendidas

def process_caixa(caixa_id, caixas, estoque, sku_corredores, top_corredores_limit, max_combinations):
    caixa_skus = caixas[caixas['CAIXA_ID'] == caixa_id][['SKU', 'PECAS']]
    sku_list = caixa_skus['SKU'].tolist()
    pecas_necessarias = dict(zip(caixa_skus['SKU'], caixa_skus['PECAS']))
    
    # Verificar se o número de SKUs é grande
    if len(sku_list) > 10:
        solution = generate_greedy_solution(sku_list, sku_corredores)
        if not solution:
            logging.error(f"Não foi possível encontrar uma solução para a caixa {caixa_id}.")
            return caixa_id, []
        # Verificar se o estoque é suficiente e calcular a distância
        estoque_suficiente = True
        corredores_usados = []
        estoque_usado = defaultdict(int)
        for idx, corredor_info in enumerate(solution):
            sku = sku_list[idx]
            pecas_estoque = corredor_info['PECAS']
            pecas_requeridas = pecas_necessarias[sku]
            if pecas_requeridas > pecas_estoque:
                logging.error(f"Estoque insuficiente para SKU {sku} no corredor {corredor_info['CORREDOR']} para a caixa {caixa_id}.")
                estoque_suficiente = False
                break
            estoque_usado[(corredor_info['ANDAR'], corredor_info['CORREDOR'], sku)] += pecas_requeridas
            # Atualizar a quantidade de peças disponíveis no corredor_info
            corredor_info['PECAS'] -= pecas_requeridas
            corredores_usados.append({'ANDAR': corredor_info['ANDAR'], 'CORREDOR': corredor_info['CORREDOR']})
        if estoque_suficiente:
            distancia = calculate_distance(corredores_usados)
            return caixa_id, [{'estoque_usado': estoque_usado, 'distancia': distancia, 'corredores': corredores_usados}]
        else:
            logging.error(f"Não foi possível atender a caixa {caixa_id} devido a estoque insuficiente.")
            return caixa_id, []
    else:
        combinations = generate_combinations(sku_list, sku_corredores, top_corredores_limit, max_combinations)
        if not combinations:
            logging.error(f"Nenhuma combinação viável encontrada para a caixa {caixa_id}.")
            return caixa_id, []
        
        solucoes_viaveis = []
        for idx_combo, combo in enumerate(combinations):
            estoque_suficiente = True
            corredores_usados = []
            estoque_usado = defaultdict(int)
            # Criar uma cópia local dos corredores para essa combinação
            combo_local = [corredor.copy() for corredor in combo]
            for idx, corredor_info in enumerate(combo_local):
                sku = sku_list[idx]
                pecas_estoque = corredor_info['PECAS']
                pecas_requeridas = pecas_necessarias[sku]
                if pecas_requeridas > pecas_estoque:
                    estoque_suficiente = False
                    break
                estoque_usado[(corredor_info['ANDAR'], corredor_info['CORREDOR'], sku)] += pecas_requeridas
                # Atualizar a quantidade de peças disponíveis no corredor_info
                corredor_info['PECAS'] -= pecas_requeridas
                corredores_usados.append({'ANDAR': corredor_info['ANDAR'], 'CORREDOR': corredor_info['CORREDOR']})
            if estoque_suficiente:
                distancia = calculate_distance(corredores_usados)
                solucoes_viaveis.append({'estoque_usado': estoque_usado, 'distancia': distancia, 'corredores': corredores_usados})
        
        if not solucoes_viaveis:
            logging.error(f"Nenhuma solução viável encontrada para a caixa {caixa_id}.")
            return caixa_id, []
        
        solucoes_viaveis.sort(key=lambda x: x['distancia'])
        melhores_solucoes_caixa = solucoes_viaveis[:3]
        return caixa_id, melhores_solucoes_caixa

def main():
    # Ler os parâmetros do arquivo YAML
    with open('../config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    
    # Extrair parâmetros
    max_combinations = config.get('max_combinations', 1000)
    top_corredores_limit = config.get('top_corredores_limit', 5)
    max_iterations = config.get('max_iterations', 5)
    data_directory = config.get('data_directory', '../data')
    output_csv = config.get('output_csv', 'resultados.csv')
    
    # Carregar os dados das caixas e do estoque
    caixas = pd.read_csv(f"{data_directory}/caixas.csv")
    estoque = pd.read_csv(f"{data_directory}/estoque.csv")
    
    # Remover duplicatas, se houver
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()
    
    # Registrar o tempo total
    tempo_inicio = time.time()
    
    # Verificar estoque suficiente para cada caixa
    caixas_sem_estoque = verificar_estoque_suficiente(caixas, estoque)
    
    if caixas_sem_estoque:
        print(f"\nCaixas que não podem ser atendidas devido a estoque insuficiente: {sorted(caixas_sem_estoque)}")
        # Remover essas caixas do conjunto de caixas a serem processadas
        caixas = caixas[~caixas['CAIXA_ID'].isin(caixas_sem_estoque)]
    else:
        print("\nTodas as caixas têm estoque suficiente para serem processadas.")
    
    # Dicionário para mapear SKU para corredores e quantidades disponíveis
    sku_corredores = update_sku_corredores(estoque)
    
    # Calcular o número de SKUs por caixa
    caixas_sku_counts = caixas.groupby('CAIXA_ID').size().reset_index(name='SKU_COUNT')
    
    # Ordenar as caixas com base no SKU_COUNT (ordem crescente)
    caixas_ids_sorted = caixas_sku_counts.sort_values('SKU_COUNT')['CAIXA_ID'].tolist()
    
    # Lista para guardar distâncias
    distancias = []
    caixas_nao_atendidas = set()
    
    # Processar as caixas
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        print(f"\nIniciando iteração {iteration}")
        caixas_nao_atendidas_iter = set()
        caixas_processadas = set()
        
        # Processar as caixas sequencialmente com barra de progresso
        melhores_solucoes = {}
        for caixa_id in tqdm(caixas_ids_sorted, desc=f"Processando caixas - Iteração {iteration}"):
            if caixa_id in caixas_nao_atendidas:
                continue  # Já tentamos essa caixa na iteração anterior sem sucesso
            caixa_id, solucoes = process_caixa(caixa_id, caixas, estoque, sku_corredores, top_corredores_limit, max_combinations)
            if solucoes:
                melhor_solucao = solucoes[0]
                distancias.append(melhor_solucao['distancia'])
                melhores_solucoes[caixa_id] = solucoes
                caixas_processadas.add(caixa_id)
                # Atualizar o estoque e as caixas com base na melhor solução
                estoque_usado = melhor_solucao['estoque_usado']
                pecas_necessarias = caixas[caixas['CAIXA_ID'] == caixa_id][['SKU', 'PECAS']].set_index('SKU')['PECAS'].to_dict()
                for (andar, corredor, sku), qtd in estoque_usado.items():
                    estoque_idx = estoque[(estoque['ANDAR'] == andar) & (estoque['CORREDOR'] == corredor) & (estoque['SKU'] == sku)].index
                    if not estoque_idx.empty:
                        estoque.loc[estoque_idx, 'PECAS'] -= qtd
                        # Remover linhas com PECAS <= 0
                        estoque = estoque[estoque['PECAS'] > 0]
                    else:
                        logging.error(f"Erro: Não foi possível encontrar o estoque para SKU {sku} no corredor {corredor}")
                # Remover os SKUs atendidos da caixa
                caixas = caixas[~((caixas['CAIXA_ID'] == caixa_id) & (caixas['SKU'].isin(pecas_necessarias.keys())))]
                # Atualizar o sku_corredores com o estoque atualizado
                sku_corredores = update_sku_corredores(estoque)
            else:
                # Caixa não pode ser preenchida
                caixas_nao_atendidas_iter.add(caixa_id)
                caixas_nao_atendidas.add(caixa_id)
        
        if not caixas_nao_atendidas_iter:
            print("\nNenhuma caixa restante para processar.")
            break  # Todas as caixas foram processadas
        elif caixas_processadas:
            print(f"\nCaixas não atendidas na iteração {iteration}: {sorted(caixas_nao_atendidas_iter)}")
            # Atualizar a lista de caixas para a próxima iteração
            caixas_ids_sorted = [cid for cid in caixas_ids_sorted if cid in caixas_nao_atendidas_iter]
        else:
            print("\nNenhuma caixa adicional pôde ser processada nesta iteração.")
            break  # Nenhuma caixa adicional pôde ser processada
    
    # Tempo total de execução
    tempo_fim = time.time()
    tempo_total = tempo_fim - tempo_inicio
    
    # Calcular a média de distância percorrida
    if distancias:
        media_distancia = sum(distancias) / len(distancias)
        print(f"\nMédia de distância percorrida: {media_distancia:.2f}")
    else:
        media_distancia = None
        print("\nNenhuma caixa foi processada com sucesso.")
    
    # Informações sobre caixas que não puderam ser preenchidas
    if caixas_nao_atendidas:
        quantidade_caixas_nao_preenchidas = len(caixas_nao_atendidas)
        caixas_nao_preenchidas_lista = sorted(caixas_nao_atendidas)
        print(f"\nQuantidade de caixas que não puderam ser preenchidas: {quantidade_caixas_nao_preenchidas}")
        print(f"\nCaixas que não puderam ser preenchidas: {caixas_nao_preenchidas_lista}")
    else:
        quantidade_caixas_nao_preenchidas = 0
        caixas_nao_preenchidas_lista = []
        print("\nTodas as caixas foram preenchidas com sucesso.")
    
    # Salvar resultados em CSV
    resultados = {
        'max_combinations': max_combinations,
        'top_corredores_limit': top_corredores_limit,
        'max_iterations': max_iterations,
        'tempo_total': tempo_total,
        'media_distancia': media_distancia,
        'quantidade_caixas_nao_preenchidas': quantidade_caixas_nao_preenchidas,
        'caixas_nao_preenchidas': caixas_nao_preenchidas_lista
    }
    
    # Verificar se o arquivo CSV já existe
    try:
        with open(output_csv, 'x', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=resultados.keys())
            writer.writeheader()
            writer.writerow(resultados)
    except FileExistsError:
        # Arquivo já existe, adicionar linha
        with open(output_csv, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=resultados.keys())
            writer.writerow(resultados)
    
    print(f"\nResultados salvos em {output_csv}")

if __name__ == '__main__':
    import cProfile
    import pstats
    import io

    pr = cProfile.Profile()
    pr.enable()

    main()  # Chamada para a função principal

    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'  # Pode ser 'tottime' ou outros critérios
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()

    # Salvar o resultado em um arquivo
    with open('profile_stats.txt', 'w') as f:
        f.write(s.getvalue())
