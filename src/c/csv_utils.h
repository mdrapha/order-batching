// csv_utils.h

#ifndef CSV_UTILS_H
#define CSV_UTILS_H

#include <stddef.h>
#include "funcoes.h"

// Funções para ler os arquivos CSV
Estoque ler_estoque(const char* filename);
Caixa* ler_caixas(const char* filename, size_t* num_caixas);

// Funções para liberar memória
void liberar_estoque(Estoque* estoque);
void liberar_caixas(Caixa* caixas, size_t num_caixas);

#endif // CSV_UTILS_H
