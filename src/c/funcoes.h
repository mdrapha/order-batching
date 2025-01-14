// funcoes.h

#ifndef FUNCOES_H
#define FUNCOES_H

#include <stddef.h>

#define MAX_SKU_LEN 50

// Estruturas de Dados

typedef struct {
    int andar;
    int corredor;
} Corredor;

typedef struct {
    int andar;
    int corredor;
    char sku[MAX_SKU_LEN];
    int pecas;
} EstoqueItem;

typedef struct {
    EstoqueItem* itens;
    size_t tamanho;
    size_t capacidade;
} Estoque;

typedef struct {
    int caixa_id;
    char sku[MAX_SKU_LEN];
    int pecas;
} CaixaItem;

typedef struct {
    CaixaItem* itens;
    size_t tamanho;
    size_t capacidade;
} Caixa;

typedef struct {
    int andar;
    int corredor;
    int pecas;
} CorredorInfo;

typedef struct {
    CorredorInfo* corredores;
    size_t tamanho;
    size_t capacidade;
} CorredorList;

typedef struct {
    char sku[MAX_SKU_LEN];
    CorredorList corredores;
} SKUCorridorMapItem;

typedef struct {
    SKUCorridorMapItem* itens;
    size_t tamanho;
    size_t capacidade;
} SKUCorridorMap;

typedef struct {
    Corredor* corredores;
    size_t tamanho;
    size_t capacidade;
    int distancia;
} Solucao;

// Protótipos de Funções

// Função para comparar corredores (usada para ordenação)
int comparar_corredores(const void* a, const void* b);

// Função para calcular a distância entre corredores
int calculate_distance(const Corredor* corredores, size_t tamanho);

// Função para atualizar o mapeamento de SKU para corredores
void atualizar_sku_corredores(const Estoque* estoque, SKUCorridorMap* sku_corredores);

// Função para gerar uma solução gulosa para uma caixa
Solucao generate_greedy_solution(const Caixa* caixa, SKUCorridorMap* sku_corredores);

// Função para processar as caixas
void processar_caixas(Caixa* caixas, size_t num_caixas, Estoque* estoque);

// Funções para liberar memória
void liberar_sku_corredores(SKUCorridorMap* sku_corredores);
void liberar_solucao(Solucao* solucao);

#endif // FUNCOES_H
