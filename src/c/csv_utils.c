// csv_utils.c

#include "csv_utils.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUFFER_SIZE 1024

// Função para ler o arquivo de estoque
Estoque ler_estoque(const char* filename) {
    Estoque estoque;
    estoque.tamanho = 0;
    estoque.capacidade = 100;
    estoque.itens = malloc(estoque.capacidade * sizeof(EstoqueItem));
    if (!estoque.itens) {
        perror("Erro ao alocar memória para o estoque");
        exit(EXIT_FAILURE);
    }

    FILE* file = fopen(filename, "r");
    if (!file) {
        perror("Erro ao abrir o arquivo de estoque");
        exit(EXIT_FAILURE);
    }

    char buffer[BUFFER_SIZE];
    // Ignorar o cabeçalho
    fgets(buffer, BUFFER_SIZE, file);

    while (fgets(buffer, BUFFER_SIZE, file)) {
        if (estoque.tamanho >= estoque.capacidade) {
            estoque.capacidade *= 2;
            estoque.itens = realloc(estoque.itens, estoque.capacidade * sizeof(EstoqueItem));
            if (!estoque.itens) {
                perror("Erro ao realocar memória para o estoque");
                fclose(file);
                exit(EXIT_FAILURE);
            }
        }

        EstoqueItem item;
        char sku[MAX_SKU_LEN];
        // Remover o caractere de nova linha
        buffer[strcspn(buffer, "\r\n")] = 0;
        sscanf(buffer, "%d,%d,%49[^,],%d", &item.andar, &item.corredor, sku, &item.pecas);
        strncpy(item.sku, sku, MAX_SKU_LEN - 1);
        item.sku[MAX_SKU_LEN - 1] = '\0'; // Garantir terminação da string
        estoque.itens[estoque.tamanho++] = item;
    }

    fclose(file);
    return estoque;
}

// Função para ler o arquivo de caixas
Caixa* ler_caixas(const char* filename, size_t* num_caixas) {
    *num_caixas = 0;
    size_t capacidade_caixas = 100;
    Caixa* caixas = malloc(capacidade_caixas * sizeof(Caixa));
    if (!caixas) {
        perror("Erro ao alocar memória para caixas");
        exit(EXIT_FAILURE);
    }

    for (size_t i = 0; i < capacidade_caixas; i++) {
        caixas[i].tamanho = 0;
        caixas[i].capacidade = 10;
        caixas[i].itens = malloc(caixas[i].capacidade * sizeof(CaixaItem));
        if (!caixas[i].itens) {
            perror("Erro ao alocar memória para itens da caixa");
            exit(EXIT_FAILURE);
        }
    }

    FILE* file = fopen(filename, "r");
    if (!file) {
        perror("Erro ao abrir o arquivo de caixas");
        exit(EXIT_FAILURE);
    }

    char buffer[BUFFER_SIZE];
    // Ignorar o cabeçalho
    fgets(buffer, BUFFER_SIZE, file);

    int ultimo_caixa_id = -1;
    size_t caixa_index = 0;

    while (fgets(buffer, BUFFER_SIZE, file)) {
        if (caixa_index >= capacidade_caixas) {
            capacidade_caixas *= 2;
            caixas = realloc(caixas, capacidade_caixas * sizeof(Caixa));
            if (!caixas) {
                perror("Erro ao realocar memória para caixas");
                fclose(file);
                exit(EXIT_FAILURE);
            }
            for (size_t i = caixa_index; i < capacidade_caixas; i++) {
                caixas[i].tamanho = 0;
                caixas[i].capacidade = 10;
                caixas[i].itens = malloc(caixas[i].capacidade * sizeof(CaixaItem));
                if (!caixas[i].itens) {
                    perror("Erro ao alocar memória para itens da caixa");
                    exit(EXIT_FAILURE);
                }
            }
        }

        CaixaItem item;
        char sku[MAX_SKU_LEN];
        // Remover o caractere de nova linha
        buffer[strcspn(buffer, "\r\n")] = 0;
        sscanf(buffer, "%d,%49[^,],%d", &item.caixa_id, sku, &item.pecas);
        strncpy(item.sku, sku, MAX_SKU_LEN - 1);
        item.sku[MAX_SKU_LEN - 1] = '\0'; // Garantir terminação da string

        if (item.caixa_id != ultimo_caixa_id) {
            if (*num_caixas > 0) {
                caixa_index++;
            }
            ultimo_caixa_id = item.caixa_id;
            (*num_caixas)++;
        }

        Caixa* caixa_atual = &caixas[caixa_index];
        if (caixa_atual->tamanho >= caixa_atual->capacidade) {
            caixa_atual->capacidade *= 2;
            caixa_atual->itens = realloc(caixa_atual->itens, caixa_atual->capacidade * sizeof(CaixaItem));
            if (!caixa_atual->itens) {
                perror("Erro ao realocar memória para itens da caixa");
                fclose(file);
                exit(EXIT_FAILURE);
            }
        }

        caixa_atual->itens[caixa_atual->tamanho++] = item;
    }

    fclose(file);
    return caixas;
}

// Função para liberar a memória alocada para o estoque
void liberar_estoque(Estoque* estoque) {
    if (estoque->itens) {
        free(estoque->itens);
        estoque->itens = NULL;
    }
    estoque->tamanho = 0;
    estoque->capacidade = 0;
}

// Função para liberar a memória alocada para as caixas
void liberar_caixas(Caixa* caixas, size_t num_caixas) {
    for (size_t i = 0; i < num_caixas; i++) {
        if (caixas[i].itens) {
            free(caixas[i].itens);
            caixas[i].itens = NULL;
        }
        caixas[i].tamanho = 0;
        caixas[i].capacidade = 0;
    }
    if (caixas) {
        free(caixas);
    }
}
