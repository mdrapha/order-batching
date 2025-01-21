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
# PARÂMETROS DE PENALIZAÇÃO
# -------------------------------------------------------
MAX_CORREDOR = 170          # Evitar corredores acima desse número
DIST_CORREDOR_PENALTY = 30  # Penalidade a ser adicionada na área se c_corr > MAX_CORREDOR

# -------------------------------------------------------
# FUNÇÕES PARA CÁLCULO DE ÁREA
# -------------------------------------------------------

def calcular_area_classe(uso_corredores_por_andar):
    """
    Calcula a área total para uma dada classe de onda,
    com base em {andar: (c_min, c_max)}.

    Exemplo simples: area = (c_max - c_min).
    Você pode ajustá-la ou usar outra forma de contar a amplitude real.
    """
    area_total = 0
    for andar, (c_min, c_max) in uso_corredores_por_andar.items():
        # Exemplo básico
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
    com uma penalização se o corredor for muito distante (c_corr > MAX_CORREDOR).
    """
    temp_uso = dict(uso_corredores_por_andar)
    if andar not in temp_uso:
        temp_uso[andar] = (corredor, corredor)
    else:
        c_min, c_max = temp_uso[andar]
        c_min = min(c_min, corredor)
        c_max = max(c_max, corredor)
        temp_uso[andar] = (c_min, c_max)

    area = calcular_area_classe(temp_uso)
    
    # Se o corredor for maior que MAX_CORREDOR, adiciona penalidade
    if corredor > MAX_CORREDOR:
        area += DIST_CORREDOR_PENALTY
    
    return area

# -------------------------------------------------------
# FUNÇÕES PARA ESTRUTURA DE ESTOQUE (DICIONÁRIO ANINHADO)
# -------------------------------------------------------

def construir_sku_corredores_aninhado(estoque):
    """
    Cria um dicionário aninhado:
      sku_corredores[SKU][ANDAR] = [ { 'CORREDOR': X, 'PECAS': Y }, ... ]
    Ordenado em ordem decrescente de PECAS, e corredor asc.
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

    for sku in sku_corredores:
        for andar in sku_corredores[sku]:
            # Ordenar cada lista por: PECAS desc, CORREDOR asc
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
# FUNÇÕES DE BUSCA
# -------------------------------------------------------

def encontrar_corredores_suficientes(sku_corredores, sku, qtd_necessaria):
    """
    Retorna uma lista de dicionários { 'ANDAR', 'CORREDOR', 'PECAS' } em que
    PECAS >= qtd_necessaria, varrendo cada andar do SKU.
    Listas estão ordenadas desc por PECAS, asc por CORREDOR.
    """
    if sku not in sku_corredores:
        return []

    resultado = []
    for andar, lista_corr in sku_corredores[sku].items():
        for info in lista_corr:
            if info['PECAS'] < qtd_necessaria:
                break
            resultado.append({
                'ANDAR': andar,
                'CORREDOR': info['CORREDOR'],
                'PECAS': info['PECAS']
            })
    return resultado


def encontrar_corredores_no_andar(sku_corredores, sku, andar, qtd_necessaria):
    """
    Retorna [ { 'CORREDOR': c, 'PECAS': p}, ... ] para um andar específico,
    com PECAS >= qtd_necessaria.
    """
    if sku not in sku_corredores:
        return []
    if andar not in sku_corredores[sku]:
        return []

    lista_corr = sku_corredores[sku][andar]
    corredores_suf = []
    for info in lista_corr:
        if info['PECAS'] < qtd_necessaria:
            break
        corredores_suf.append(info)
    return corredores_suf


# -------------------------------------------------------
# FUNÇÃO Fallback (FORÇAR ATENDIMENTO)
# -------------------------------------------------------

def forcar_atender_skus(skus_necessarios, sku_corredores, uso_corredores_por_andar, caixa_id=None):
    """
    Fallback "parcial": atende somente os SKUs passados em 'skus_necessarios',
    sem se importar com a área (apenas atualizando se for além do MAX_CORREDOR).
    Retorna lista de (andar, corredor, sku, qtd).
    """
    resultado_forcado = []
    for sku, qtd_needed in skus_necessarios.items():
        qtd_restante = qtd_needed

        if sku not in sku_corredores:
            logging.error(f"[Fallback] SKU {sku} não encontrado (caixa={caixa_id})")
            continue

        for andar in list(sku_corredores[sku].keys()):
            lista_corr = sku_corredores[sku][andar]
            i = 0
            while i < len(lista_corr):
                info = lista_corr[i]
                if info['PECAS'] > 0:
                    qtd_possivel = min(info['PECAS'], qtd_restante)
                    info['PECAS'] -= qtd_possivel
                    qtd_restante -= qtd_possivel

                    # Atualizar área
                    atualizar_area_classe(uso_corredores_por_andar, andar, info['CORREDOR'])
                    # Registrar
                    resultado_forcado.append((andar, info['CORREDOR'], sku, qtd_possivel))

                    if info['PECAS'] <= 0:
                        lista_corr.pop(i)
                        i -= 1
                    if qtd_restante <= 0:
                        break
                i += 1

            if len(lista_corr) == 0:
                sku_corredores[sku].pop(andar, None)

            if qtd_restante <= 0:
                break

        if qtd_restante > 0:
            logging.error(f"[Fallback] Não foi possível atender SKU={sku}, rest={qtd_restante}, caixa={caixa_id}")

    return resultado_forcado


# -------------------------------------------------------
# ORGANIZAR CAIXAS POR CLASSE
# -------------------------------------------------------

def organizar_caixas_por_classe(caixas):
    """
    Agrupa as caixas por CLASSE_ONDA, retornando {classe: df}.
    """
    classes = {}
    for classe_onda, group in caixas.groupby('CLASSE_ONDA'):
        classes[classe_onda] = group.copy()
    return classes


# -------------------------------------------------------
# PROCESSAMENTO DE UMA CLASSE
# -------------------------------------------------------

def processar_classe_onda(caixas_classe, sku_corredores):
    """
    Faz:
      1) Single-corridor
      2) Multi-corridor com penalização p/ corredores distantes
      3) Fallback PARCIAL somente p/ SKUs que não foram atendidos
    Retorna soluções, área (antes e depois fallback), etc.
    """
    solucoes_por_caixa = {}
    uso_corredores_por_andar = {}
    caixas_fallback = set()

    caixa_ids = caixas_classe['CAIXA_ID'].unique()

    # A) Identificar single-corridor vs multi-corridor
    single_corridor_caixas = []
    multi_corridor_caixas = []
    for caixa_id in caixa_ids:
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()

        # Verificar se existe 1 corredor que supra todos os SKUs
        sets_corr = []
        for sku, qtd in skus_pecas.items():
            cands = encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            set_cand = set((c['ANDAR'], c['CORREDOR']) for c in cands)
            sets_corr.append(set_cand)

        corredores_comuns = set.intersection(*sets_corr) if sets_corr else set()
        if corredores_comuns:
            single_corridor_caixas.append(caixa_id)
        else:
            multi_corridor_caixas.append(caixa_id)

    # -------------------------------------------------------
    # SINGLE-CORRIDOR
    # -------------------------------------------------------
    for caixa_id in tqdm(single_corridor_caixas, desc="Processando caixas Single-Corridor"):
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()

        # Interseção de corredores
        sets_corr = []
        for sku, qtd in skus_pecas.items():
            cands = encontrar_corredores_suficientes(sku_corredores, sku, qtd)
            set_cand = set((c['ANDAR'], c['CORREDOR']) for c in cands)
            sets_corr.append(set_cand)
        corredores_comuns = set.intersection(*sets_corr) if sets_corr else set()

        if not corredores_comuns:
            # Fallback total p/ essa caixa
            solucoes_por_caixa[caixa_id] = None
            caixas_fallback.add(caixa_id)
            continue

        # Escolher corredor minimizando a "área_incluir" (com penalização se > MAX_CORREDOR)
        melhor_corr = None
        melhor_aumento = float('inf')
        for (andar, cor) in corredores_comuns:
            area_atual = calcular_area_classe(uso_corredores_por_andar)
            area_incl = calcular_area_se_incluir(uso_corredores_por_andar, andar, cor)
            aumento = area_incl - area_atual
            if aumento < melhor_aumento:
                melhor_aumento = aumento
                melhor_corr = (andar, cor)

        if melhor_corr:
            andar_, cor_ = melhor_corr
            atualizar_area_classe(uso_corredores_por_andar, andar_, cor_)
            # Decrementar do estoque
            for sku, qtd_req in skus_pecas.items():
                decrementa_estoque(sku_corredores, sku, andar_, cor_, qtd_req)
            solucoes_por_caixa[caixa_id] = {'andar_corredor': melhor_corr}
        else:
            solucoes_por_caixa[caixa_id] = None
            caixas_fallback.add(caixa_id)

    # -------------------------------------------------------
    # MULTI-CORRIDOR
    # -------------------------------------------------------
    for caixa_id in tqdm(multi_corridor_caixas, desc="Processando caixas Multi-Corridor"):
        df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
        skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()

        # Precisamos iterar “SKU a SKU”
        skus_restantes = dict(skus_pecas)
        corredores_usados = []

        # Montar info de densidade por andar
        andar_info = {}
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
            dens_ = total_p / area_a if area_a else 0
            densidade_por_andar.append((andar_, dens_))

        # Ordenar do maior p/ menor
        densidade_por_andar.sort(key=lambda x: x[1], reverse=True)

        for (andar_, dens_) in densidade_por_andar:
            if not skus_restantes:
                break

            # Tentar atender parte dos SKUs nesse andar
            skus_atendidos_agora = []
            for sku, qtd_req in list(skus_restantes.items()):
                cands = encontrar_corredores_no_andar(sku_corredores, sku, andar_, qtd_req)
                if not cands:
                    continue

                # Escolher corredor que minimize aumento
                melhor_corr = None
                melhor_aumento = float('inf')
                for cinfo in cands:
                    cor__ = cinfo['CORREDOR']
                    area_atual = calcular_area_classe(uso_corredores_por_andar)
                    area_incl = calcular_area_se_incluir(uso_corredores_por_andar, andar_, cor__)
                    aumento = area_incl - area_atual
                    if aumento < melhor_aumento:
                        melhor_aumento = aumento
                        melhor_corr = cinfo

                if melhor_corr:
                    cor__ = melhor_corr['CORREDOR']
                    atualizar_area_classe(uso_corredores_por_andar, andar_, cor__)
                    decrementa_estoque(sku_corredores, sku, andar_, cor__, qtd_req)
                    corredores_usados.append((andar_, cor__, sku, qtd_req))
                    skus_atendidos_agora.append(sku)

            # Remover SKUs atendidos
            for sku_at in skus_atendidos_agora:
                skus_restantes.pop(sku_at, None)

        # Ao final, se ainda restou algo, faremos fallback PARCIAL SÓ p/ esses SKUs
        if skus_restantes:
            caixas_fallback.add(caixa_id)
            # Registrar no solucoes_por_caixa o que foi feito na heurística
            partial_sol = list(corredores_usados)  # clone
            solucoes_por_caixa[caixa_id] = partial_sol

            # Fallback APENAS p/ SKUs que sobraram
            logging.warning(f"[Fallback parcial] Caixa {caixa_id} -> {list(skus_restantes.keys())}")
            fallback_sol = forcar_atender_skus(skus_restantes, sku_corredores, uso_corredores_por_andar, caixa_id=caixa_id)
            # Anexa o fallback ao partial
            solucoes_por_caixa[caixa_id].extend(fallback_sol)
        else:
            solucoes_por_caixa[caixa_id] = corredores_usados

    # (2) Área antes de qualquer fallback total
    #    (Observando que já houve fallback parcial do multi-corridor, mas não de single-corr)
    area_before_fallback = calcular_area_classe(uso_corredores_por_andar)

    # -------------------------------------------------------
    # D) Tratar CAIXAS single-corridor que ficaram com 'None'
    #    -> fallback total
    # -------------------------------------------------------
    for caixa_id in caixa_ids:
        if solucoes_por_caixa[caixa_id] is None:
            # Fallback total p/ todos SKUs
            df_caixa = caixas_classe[caixas_classe['CAIXA_ID'] == caixa_id]
            skus_pecas = df_caixa.groupby('SKU')['PECAS'].sum().to_dict()
            forced_sol = forcar_atender_skus(skus_pecas, sku_corredores, uso_corredores_por_andar, caixa_id)
            solucoes_por_caixa[caixa_id] = forced_sol

    # (4) Área final depois do fallback
    area_after_fallback = calcular_area_classe(uso_corredores_por_andar)

    return solucoes_por_caixa, area_before_fallback, area_after_fallback, uso_corredores_por_andar, caixas_fallback


# -------------------------------------------------------
# FLUXO PRINCIPAL
# -------------------------------------------------------
def main():
    # Ler CSV
    caixas = pd.read_csv("data/caixas.csv")
    estoque = pd.read_csv("data/estoque.csv")

    # Remover duplicatas
    caixas = caixas.drop_duplicates()
    estoque = estoque.drop_duplicates()

    # Construir dicionário aninhado
    sku_corredores = construir_sku_corredores_aninhado(estoque)

    # Agrupar as caixas por classe
    caixas_por_classe = organizar_caixas_por_classe(caixas)

    # Processar
    resultados = {}
    for classe_onda, caixas_classe in caixas_por_classe.items():
        print(f"\n=== Processando classe: {classe_onda} ===")
        (solucoes,
         area_before,
         area_after,
         uso_corr,
         caixas_fallback) = processar_classe_onda(caixas_classe, sku_corredores)

        resultados[classe_onda] = {
            'solucoes': solucoes,
            'area_before_fallback': area_before,
            'area_after_fallback': area_after,
            'uso_corredores_por_andar': uso_corr,
            'caixas_fallback': caixas_fallback
        }

    print("\n=== RESULTADOS ===")
    for classe_onda, info in resultados.items():
        print(f"\nClasse {classe_onda}:")
        print(f" - Área antes fallback: {info['area_before_fallback']:.2f}")
        print(f" - Área depois fallback: {info['area_after_fallback']:.2f}")
        if info['caixas_fallback']:
            print(f" - Caixas fallback: {len(info['caixas_fallback'])}")
        else:
            print(" - Nenhuma caixa precisou fallback")

        # Mostrar andares e amplitude
        uso_por_andar = info['uso_corredores_por_andar']
        if uso_por_andar:
            print(" - Andares usados e amplitude:")
            for andar_ in sorted(uso_por_andar.keys()):
                c_min, c_max = uso_por_andar[andar_]
                total_corr = (c_max - c_min) + 1
                print(f"   Andar {andar_}: c_min={c_min}, c_max={c_max}, total_corredores={total_corr}")
        else:
            print(" - Nenhum andar utilizado")

    print("\nFim do processamento.")


if __name__ == "__main__":
    main()