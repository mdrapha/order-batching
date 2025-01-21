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
    com base em {andar: (c_min, c_max)}.

    Exemplo simples: area = (c_max - c_min).
    Ajuste conforme sua regra de par/ímpar ou penalidade de andar.
    """
    area_total = 0
    for andar, (c_min, c_max) in uso_corredores_por_andar.items():
        # Exemplo básico: área do andar = (c_max - c_min)
        area_total += (c_max - c_min)
    return area_total


def atualizar_area_classe(uso_corredores_por_andar, andar, corredor):
    """
    Atualiza (c_min, c_max) do dicionário uso_corredores_por_andar,
    considerando o novo corredor acessado.
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
    Calcula a área total caso inclua (andar, corredor) temporariamente,
    sem alterar permanentemente 'uso_corredores_por_andar'.
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

    # Ordenar cada lista por PECAS desc, depois CORREDOR asc
    for sku in sku_corredores:
        for andar in sku_corredores[sku]:
            sku_corredores[sku][andar].sort(
                key=lambda x: (-x['PECAS'], x['CORREDOR'])
            )

    return sku_corredores


def decrementa_estoque(sku_corredores, sku, andar, corredor, qtd_retirada):
    """
    Decrementa 'qtd_retirada' do corredor específico (sku, andar, corredor).
    Remove-o se ficar com 0 ou menos PECAS.
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
                corredores_list.pop(i)
            break

    if len(corredores_list) == 0:
        sku_corredores[sku].pop(andar, None)


# -------------------------------------------------------
# FUNÇÕES DE BUSCA DE CORREDORES
# -------------------------------------------------------

def encontrar_corredores_suficientes(sku_corredores, sku, qtd_necessaria):
    """
    Percorre cada andar desse SKU e retorna
    [ {'ANDAR': a, 'CORREDOR': c, 'PECAS': p}, ... ]
    onde p >= qtd_necessaria.

    As listas já estão ordenadas por PECAS desc,
    então interrompemos no momento em que p < qtd_necessaria.
    """
    if sku not in sku_corredores:
        return []

    resultado = []
    for andar, lista_corredores in sku_corredores[sku].items():
        for info in lista_corredores:
            if info['PECAS'] < qtd_necessaria:
                # Como está em desc, não há mais neste andar
                break
            resultado.append({
                'ANDAR': andar,
                'CORREDOR': info['CORREDOR'],
                'PECAS': info['PECAS']
            })
    return resultado


def encontrar_corredores_no_andar(sku_corredores, sku, andar, qtd_necessaria):
    """
    Busca corredores somente em um andar, retornando
    [{'CORREDOR': c, 'PECAS': p}, ...] com p >= qtd_necessaria.
    """
    if sku not in sku_corredores:
        return []
    if andar not in sku_corredores[sku]:
        return []

    lista_corredores = sku_corredores[sku][andar]
    corredores_suficientes = []
    for info in lista_corredores:
        if info['PECAS'] < qtd_necessaria:
            break
        corredores_suficientes.append(info)
    return corredores_suficientes


# -------------------------------------------------------
# FUNÇÃO Fallback (FORÇAR ATENDIMENTO)
# -------------------------------------------------------

def forcar_atender_caixa(caixa_id, skus_necessarios, sku_corredores, uso_corredores_por_andar):
    """
    Garante que a caixa seja totalmente atendida,
    independentemente da área (estoque total é suficiente).

    Retorna uma lista de tuplas (andar, corredor, sku, qtd),
    e atualiza o dicionário 'sku_corredores'.

    Também atualiza a área (uso_corredores_por_andar)
    para cada corredor que precisarmos acessar no fallback.
    """
    resultado_forcado = []

    for sku, qtd_needed in skus_necessarios.items():
        qtd_restante = qtd_needed

        # Percorrer todos os andares e corredores do SKU
        if sku not in sku_corredores:
            logging.error(f"[Fallback] SKU {sku} não encontrado no estoque. (Caixa={caixa_id})")
            continue

        for andar in list(sku_corredores[sku].keys()):
            corredores_list = sku_corredores[sku][andar]
            i = 0
            while i < len(corredores_list):
                info = corredores_list[i]
                if info['PECAS'] > 0:
                    # Retiramos o máximo possível
                    qtd_possivel = min(info['PECAS'], qtd_restante)
                    info['PECAS'] -= qtd_possivel
                    qtd_restante -= qtd_possivel

                    # Registrar no resultado
                    resultado_forcado.append((andar, info['CORREDOR'], sku, qtd_possivel))

                    # Atualizar a área percorrida
                    atualizar_area_classe(uso_corredores_por_andar, andar, info['CORREDOR'])

                    if info['PECAS'] <= 0:
                        corredores_list.pop(i)
                        i -= 1
                    if qtd_restante <= 0:
                        break
                i += 1

            if len(corredores_list) == 0:
                # Remove o andar se ficou vazio
                sku_corredores[sku].pop(andar, None)

            if qtd_restante <= 0:
                break

        if qtd_restante > 0:
            # Teoricamente não deveria acontecer se SEMPRE há estoque suficiente
            logging.error(f"[Fallback] Estoque insuficiente pro SKU={sku}, rest={qtd_restante}, caixa={caixa_id}")

    return resultado_forcado


# -------------------------------------------------------
# ORGANIZAR CAIXAS POR CLASSE
# -------------------------------------------------------

def organizar_caixas_por_classe(caixas):
    """
    Retorna {classe_onda: DataFrame}.
    """
    classes = {}
    for classe_onda, group in caixas.groupby('CLASSE_ONDA'):
        classes[classe_onda] = group.copy()
    return classes


# -------------------------------------------------------
# FUNÇÃO PRINCIPAL DE PROCESSAMENTO DA CLASSE
# -------------------------------------------------------
def processar_classe_onda(caixas_classe, sku_corredores):
    """
    1) Resolve caixas single-corridor e multi-corridor pela heurística;
    2) Calcula area_before_fallback
    3) Se alguma caixa não foi atendida, executa fallback para garantir atendimento.
    4) Calcula area_after_fallback
    5) Retorna:
       - solucoes_por_caixa
       - area_before_fallback
       - area_after_fallback
       - uso_corredores_por_andar (para sabermos quais andares foram usados)
       - caixas_fallback (conjunto das caixas que usaram fallback)
    """
    solucoes_por_caixa = {}
    uso_corredores_por_andar = {}
    caixas_fallback = set()  # rastreia quais caixas não foram atendidas pela heurística

    caixa_ids = caixas_classe['CAIXA_ID'].unique()
    single_corridor_caixas = []
    multi_corridor_caixas = []

    # 1) Separar single e multi-corridor
    for caixa_id in caixa_ids:
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()

        # Verificar se existe 1 corredor que supra todos os SKUs
        sets_corr = []
        for sku, qtd in skus_pecas.items():
            cands = encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            s = set((x['ANDAR'], x['CORREDOR']) for x in cands)
            sets_corr.append(s)

        if sets_corr:
            corredores_comuns = set.intersection(*sets_corr)
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

        # Interseção de corredores
        sets_corr = []
        for sku, qtd in skus_pecas.items():
            cands = encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            s = set((x['ANDAR'], x['CORREDOR']) for x in cands)
            sets_corr.append(s)

        corredores_comuns = set.intersection(*sets_corr) if sets_corr else set()

        if not corredores_comuns:
            solucoes_por_caixa[caixa_id] = None
            caixas_fallback.add(caixa_id)
            logging.warning(f"Caixa {caixa_id} (single-corr) não atendida na heurística -> fallback.")
            continue

        # Escolher o corredor que minimize o aumento de área
        melhor_corr = None
        melhor_aumento = float('inf')

        for (andar, cor) in corredores_comuns:
            area_atual = calcular_area_classe(uso_corredores_por_andar)
            area_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar, cor)
            aumento = area_incluir - area_atual
            if aumento < melhor_aumento:
                melhor_aumento = aumento
                melhor_corr = (andar, cor)

        if melhor_corr is None:
            solucoes_por_caixa[caixa_id] = None
            caixas_fallback.add(caixa_id)
            logging.warning(f"Caixa {caixa_id} (single-corr) sem corredor escolhido -> fallback.")
            continue

        # Decrementa estoque para todos os SKUs
        andar_s, cor_s = melhor_corr
        atualizar_area_classe(uso_corredores_por_andar, andar_s, cor_s)

        for sku, qtd_req in skus_pecas.items():
            decrementa_estoque(sku_corredores, sku, andar_s, cor_s, qtd_req)

        solucoes_por_caixa[caixa_id] = {'andar_corredor': melhor_corr}

    # -------------------------------------------------------
    # B) MULTI-CORRIDOR
    # -------------------------------------------------------
    for caixa_id in tqdm(multi_corridor_caixas, desc="Processando caixas Multi-Corridor"):
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()

        skus_restantes = dict(skus_pecas)
        corredores_utilizados = []

        # Montar densidade por andar
        andar_info = {}
        # Percorre todo sku_corredores
        for sku_ in sku_corredores:
            for andar_ in sku_corredores[sku_]:
                for corinfo in sku_corredores[sku_][andar_]:
                    if andar_ not in andar_info:
                        andar_info[andar_] = {
                            'corr_min': corinfo['CORREDOR'],
                            'corr_max': corinfo['CORREDOR'],
                            'total_pecas': corinfo['PECAS']
                        }
                    else:
                        andar_info[andar_]['corr_min'] = min(andar_info[andar_]['corr_min'], corinfo['CORREDOR'])
                        andar_info[andar_]['corr_max'] = max(andar_info[andar_]['corr_max'], corinfo['CORREDOR'])
                        andar_info[andar_]['total_pecas'] += corinfo['PECAS']

        densidade_por_andar = []
        for andar_ in andar_info:
            cmin = andar_info[andar_]['corr_min']
            cmax = andar_info[andar_]['corr_max']
            area_a = (cmax - cmin) + 1
            total_p = andar_info[andar_]['total_pecas']
            dens = total_p / area_a if area_a else 0
            densidade_por_andar.append((andar_, dens))

        # Ordenar do maior para o menor
        densidade_por_andar.sort(key=lambda x: x[1], reverse=True)

        # Tentar atender no andar com maior densidade primeiro
        for (andar_, dens_) in densidade_por_andar:
            if not skus_restantes:
                break

            skus_atendidos = []
            for sku, qtd_req in list(skus_restantes.items()):
                cands = encontrar_corredores_no_andar(sku_corredores, sku, andar_, qtd_req)
                if not cands:
                    continue

                # Escolher corredor que minimize aumento de área
                melhor_corr = None
                melhor_aumento = float('inf')
                for cinfo in cands:
                    cor_ = cinfo['CORREDOR']
                    area_atual = calcular_area_classe(uso_corredores_por_andar)
                    area_incluir = calcular_area_se_incluir(uso_corredores_por_andar, andar_, cor_)
                    aumento = area_incluir - area_atual
                    if aumento < melhor_aumento:
                        melhor_aumento = aumento
                        melhor_corr = cinfo

                if melhor_corr:
                    atualizar_area_classe(uso_corredores_por_andar, andar_, melhor_corr['CORREDOR'])
                    decrementa_estoque(sku_corredores, sku, andar_, melhor_corr['CORREDOR'], qtd_req)
                    corredores_utilizados.append((andar_, melhor_corr['CORREDOR'], sku, qtd_req))
                    skus_atendidos.append(sku)

            for s_ in skus_atendidos:
                skus_restantes.pop(s_, None)

        if skus_restantes:
            # Não foi totalmente atendida pela heurística
            solucoes_por_caixa[caixa_id] = None
            caixas_fallback.add(caixa_id)
            logging.warning(f"Caixa {caixa_id} (multi-corr) incompleta na heurística -> fallback.")
        else:
            solucoes_por_caixa[caixa_id] = corredores_utilizados

    # -------------------------------------------------------
    # (2) Calcular area_before_fallback
    # -------------------------------------------------------
    area_before_fallback = calcular_area_classe(uso_corredores_por_andar)

    # -------------------------------------------------------
    # C) Fallback: Forçar atendimento de caixas não atendidas
    # -------------------------------------------------------
    for caixa_id in caixa_ids:
        if solucoes_por_caixa[caixa_id] is None:
            df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
            skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()

            logging.warning(f"[Fallback] Forçando atendimento para caixa {caixa_id}")
            resultado_forced = forcar_atender_caixa(caixa_id, skus_pecas, sku_corredores, uso_corredores_por_andar)

            # Salva como solução final (mesmo que seja fallback)
            solucoes_por_caixa[caixa_id] = resultado_forced

    # (4) Calcular area_after_fallback
    area_after_fallback = calcular_area_classe(uso_corredores_por_andar)

    return (
        solucoes_por_caixa,
        area_before_fallback,
        area_after_fallback,
        uso_corredores_por_andar,
        caixas_fallback
    )


# -------------------------------------------------------
# FLUXO PRINCIPAL
# -------------------------------------------------------

def main():
    # Ler os arquivos CSV
    caixas = pd.read_csv("data/caixas.csv")   # colunas: CAIXA_ID, SKU, CLASSE_ONDA, PECAS
    estoque = pd.read_csv("data/estoque.csv") # colunas: ANDAR, CORREDOR, SKU, PECAS

    # Remover duplicatas
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()

    # Construir o dicionário aninhado
    sku_corredores = construir_sku_corredores_aninhado(estoque)

    # Agrupar as caixas por classe de onda
    caixas_por_classe = organizar_caixas_por_classe(caixas)

    resultados = {}
    for classe_onda, caixas_classe in caixas_por_classe.items():
        print(f"\n=== Processando classe de onda: {classe_onda} ===")
        (solucoes_classe,
         area_before,
         area_after,
         uso_corr,
         caixas_fallback) = processar_classe_onda(caixas_classe, sku_corredores)

        resultados[classe_onda] = {
            'solucoes': solucoes_classe,
            'area_before_fallback': area_before,
            'area_after_fallback': area_after,
            'uso_corredores_por_andar': uso_corr,
            'caixas_fallback': caixas_fallback
        }

    # -------------------------------------------------------
    # EXIBIR RESULTADOS CONFORME PEDIDO
    # -------------------------------------------------------
    print("\n=== RESULTADOS FINAIS ===")
    for classe_onda, info in resultados.items():
        print(f"\nClasse {classe_onda}:")

        # 1) Mostrar área antes e depois do fallback
        print(f"  Área antes do fallback: {info['area_before_fallback']:.2f}")
        print(f"  Área depois do fallback: {info['area_after_fallback']:.2f}")

        # 2) Mostrar as caixas que NÃO foram atendidas pela heurística (usaram fallback)
        #    Se não houve fallback para nenhuma caixa, não imprime nada.
        if info['caixas_fallback']:
            print(f"  Quantidade  de caixas que precisaram de fallback: {len(info['caixas_fallback'])}")
        else:
            print("  Nenhuma caixa precisou de fallback (todas foram atendidas pela heurística).")

        # 3) Mostrar andares usados e a quantidade máxima de corredores
        uso_por_andar = info['uso_corredores_por_andar']
        if not uso_por_andar:
            print("  Nenhum andar foi usado (possível que não houvesse caixas).")
            continue

        print("  Andares efetivamente usados e quantidade de corredores:")
        for andar_ in sorted(uso_por_andar.keys()):
            c_min, c_max = uso_por_andar[andar_]
            total_corredores = (c_max - c_min) + 1
            print(f"    Andar {andar_}: c_min={c_min}, c_max={c_max}, total_corredores={total_corredores}")

    print("\nProcessamento concluído.")


if __name__ == "__main__":
    main()