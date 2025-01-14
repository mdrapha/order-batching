// funcoes.c

#include "funcoes.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Função para comparar corredores (usada para ordenação)
int comparar_corredores(const void* a, const void* b) {
    const Corredor* c1 = (const Corredor*)a;
    const Corredor* c2 = (const Corredor*)b;
    if (c1->andar != c2->andar) {
        return c1->andar - c2->andar;
    }
    return c1->corredor - c2->corredor;
}

// Função para calcular a distância entre corredores
int calculate_distance(const Corredor* corredores, size_t tamanho) {
    if (tamanho == 0) return 0;

    Corredor* corredores_ordenados = malloc(tamanho * sizeof(Corredor));
    if (!corredores_ordenados) {
        perror("Erro ao alocar memória para corredores_ordenados");
        exit(EXIT_FAILURE);
    }
    memcpy(corredores_ordenados, corredores, tamanho * sizeof(Corredor));
    qsort(corredores_ordenados, tamanho, sizeof(Corredor), comparar_corredores);

    int total_distance = 0;
    for (size_t i = 0; i < tamanho - 1; i++) {
        const Corredor* c1 = &corredores_ordenados[i];
        const Corredor* c2 = &corredores_ordenados[i + 1];
        int dist = abs(c1->corredor - c2->corredor);
        if (c1->andar != c2->andar) {
            dist += 10; // Penalidade para mudança de andar
        }
        total_distance += dist;
    }

    free(corredores_ordenados);
    return total_distance;
}

// Função para atualizar o mapeamento de SKU para corredores
void atualizar_sku_corredores(const Estoque* estoque, SKUCorridorMap* sku_corredores) {
    sku_corredores->tamanho = 0;
    sku_corredores->capacidade = 100;
    sku_corredores->itens = malloc(sku_corredores->capacidade * sizeof(SKUCorridorMapItem));
    if (!sku_corredores->itens) {
        perror("Erro ao alocar memória para sku_corredores");
        exit(EXIT_FAILURE);
    }

    for (size_t i = 0; i < estoque->tamanho; i++) {
        const EstoqueItem* item = &estoque->itens[i];
        // Verificar se o SKU já está no mapa
        int encontrado = 0;
        for (size_t j = 0; j < sku_corredores->tamanho; j++) {
            if (strcmp(sku_corredores->itens[j].sku, item->sku) == 0) {
                // Adicionar corredor à lista
                CorredorInfo ci;
                ci.andar = item->andar;
                ci.corredor = item->corredor;
                ci.pecas = item->pecas;

                CorredorList* cl = &sku_corredores->itens[j].corredores;
                if (cl->tamanho >= cl->capacidade) {
                    cl->capacidade *= 2;
                    cl->corredores = realloc(cl->corredores, cl->capacidade * sizeof(CorredorInfo));
                    if (!cl->corredores) {
                        perror("Erro ao realocar memória para corredores");
                        exit(EXIT_FAILURE);
                    }
                }
                cl->corredores[cl->tamanho++] = ci;
                encontrado = 1;
                break;
            }
        }
        if (!encontrado) {
            // Adicionar novo SKU ao mapa
            if (sku_corredores->tamanho >= sku_corredores->capacidade) {
                sku_corredores->capacidade *= 2;
                sku_corredores->itens = realloc(sku_corredores->itens, sku_corredores->capacidade * sizeof(SKUCorridorMapItem));
                if (!sku_corredores->itens) {
                    perror("Erro ao realocar memória para sku_corredores");
                    exit(EXIT_FAILURE);
                }
            }
            SKUCorridorMapItem new_item;
            strncpy(new_item.sku, item->sku, MAX_SKU_LEN - 1);
            new_item.sku[MAX_SKU_LEN - 1] = '\0';
            new_item.corredores.tamanho = 0;
            new_item.corredores.capacidade = 10;
            new_item.corredores.corredores = malloc(new_item.corredores.capacidade * sizeof(CorredorInfo));
            if (!new_item.corredores.corredores) {
                perror("Erro ao alocar memória para corredores");
                exit(EXIT_FAILURE);
            }
            // Adicionar corredor
            CorredorInfo ci;
            ci.andar = item->andar;
            ci.corredor = item->corredor;
            ci.pecas = item->pecas;
            new_item.corredores.corredores[new_item.corredores.tamanho++] = ci;

            sku_corredores->itens[sku_corredores->tamanho++] = new_item;
        }
    }
}

// Função para gerar uma solução gulosa para uma caixa
Solucao generate_greedy_solution(const Caixa* caixa, SKUCorridorMap* sku_corredores) {
    Solucao solucao;
    solucao.tamanho = 0;
    solucao.capacidade = caixa->tamanho;
    solucao.corredores = malloc(solucao.capacidade * sizeof(Corredor));
    if (!solucao.corredores) {
        perror("Erro ao alocar memória para solucao.corredores");
        exit(EXIT_FAILURE);
    }
    solucao.distancia = 0;

    for (size_t i = 0; i < caixa->tamanho; i++) {
        const CaixaItem* ci = &caixa->itens[i];
        // Encontrar o SKU no mapa
        int encontrado = 0;
        for (size_t j = 0; j < sku_corredores->tamanho; j++) {
            if (strcmp(sku_corredores->itens[j].sku, ci->sku) == 0) {
                // Selecionar o melhor corredor que tenha quantidade suficiente
                CorredorList* cl = &sku_corredores->itens[j].corredores;
                for (size_t k = 0; k < cl->tamanho; k++) {
                    CorredorInfo* corredor_info = &cl->corredores[k];
                    if (corredor_info->pecas >= ci->pecas) {
                        // Encontrou um corredor que tem peças suficientes
                        Corredor corredor;
                        corredor.andar = corredor_info->andar;
                        corredor.corredor = corredor_info->corredor;
                        // Adicionar à solução
                        solucao.corredores[solucao.tamanho++] = corredor;

                        // Atualizar a quantidade de peças no corredor_info
                        corredor_info->pecas -= ci->pecas;
                        encontrado = 1;
                        break;
                    }
                }
                break; // Encontramos o SKU, saímos do loop
            }
        }
        if (!encontrado) {
            // Não foi possível encontrar o SKU com quantidade suficiente
            solucao.tamanho = 0;
            break;
        }
    }

    if (solucao.tamanho > 0) {
        solucao.distancia = calculate_distance(solucao.corredores, solucao.tamanho);
    } else {
        solucao.distancia = -1;
    }

    return solucao;
}

// Função para processar as caixas
void processar_caixas(Caixa* caixas, size_t num_caixas, Estoque* estoque) {
    for (size_t i = 0; i < num_caixas; i++) {
        // Atualizar o mapa de SKU para corredores
        SKUCorridorMap sku_corredores;
        atualizar_sku_corredores(estoque, &sku_corredores);

        Caixa* caixa = &caixas[i];
        // Gerar solução para a caixa
        Solucao solucao = generate_greedy_solution(caixa, &sku_corredores);
        if (solucao.distancia >= 0) {
            // Solução encontrada
            printf("Caixa %d: Distância = %d\n", caixa->itens[0].caixa_id, solucao.distancia);
            // Atualizar estoque
            for (size_t j = 0; j < caixa->tamanho; j++) {
                const CaixaItem* ci = &caixa->itens[j];
                const Corredor* corredor_usado = &solucao.corredores[j];
                // Encontrar o item correspondente no estoque
                for (size_t k = 0; k < estoque->tamanho; k++) {
                    EstoqueItem* estoque_item = &estoque->itens[k];
                    if (strcmp(estoque_item->sku, ci->sku) == 0 &&
                        estoque_item->andar == corredor_usado->andar &&
                        estoque_item->corredor == corredor_usado->corredor) {
                        // Atualizar o estoque
                        estoque_item->pecas -= ci->pecas;
                        if (estoque_item->pecas < 0) {
                            printf("Erro: estoque negativo para SKU %s no corredor %d\n", ci->sku, estoque_item->corredor);
                        }
                        break;
                    }
                }
            }
            // Remover itens com 0 peças do estoque
            size_t novo_tamanho = 0;
            for (size_t k = 0; k < estoque->tamanho; k++) {
                if (estoque->itens[k].pecas > 0) {
                    estoque->itens[novo_tamanho++] = estoque->itens[k];
                }
            }
            estoque->tamanho = novo_tamanho;
        } else {
            // Não foi possível atender a caixa
            printf("Caixa %d: Não foi possível atender\n", caixa->itens[0].caixa_id);
        }
        liberar_solucao(&solucao);
        liberar_sku_corredores(&sku_corredores);
    }
}


void liberar_sku_corredores(SKUCorridorMap* sku_corredores) {
    for (size_t i = 0; i < sku_corredores->tamanho; i++) {
        if (sku_corredores->itens[i].corredores.corredores) {
            free(sku_corredores->itens[i].corredores.corredores);
            sku_corredores->itens[i].corredores.corredores = NULL;
        }
        sku_corredores->itens[i].corredores.tamanho = 0;
        sku_corredores->itens[i].corredores.capacidade = 0;
    }
    if (sku_corredores->itens) {
        free(sku_corredores->itens);
        sku_corredores->itens = NULL;
    }
    sku_corredores->tamanho = 0;
    sku_corredores->capacidade = 0;
}

void liberar_solucao(Solucao* solucao) {
    if (solucao->corredores) {
        free(solucao->corredores);
        solucao->corredores = NULL;
    }
    solucao->tamanho = 0;
    solucao->capacidade = 0;
    solucao->distancia = 0;
}
