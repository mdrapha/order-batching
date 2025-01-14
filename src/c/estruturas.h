// estruturas.h
#ifndef ESTRUTURAS_H
#define ESTRUTURAS_H
#include <stddef.h>

#define MAX_SKU_LEN 50

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
    int andar;
    int corredor;
} Corredor;

typedef struct {
    Corredor* corredores;
    size_t tamanho;
    size_t capacidade;
    int distancia;
} Solucao;

#endif // ESTRUTURAS_H
