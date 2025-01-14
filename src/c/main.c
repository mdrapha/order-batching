// main.c

#include <stdio.h>
#include <stdlib.h>
#include "csv_utils.h"
#include "funcoes.h"

int main() {
    // Carregar dados do estoque e das caixas
    Estoque estoque = ler_estoque("../../data/estoque.csv");

    size_t num_caixas;
    Caixa* caixas = ler_caixas("../../data/caixas.csv", &num_caixas);

    // Processar as caixas
    processar_caixas(caixas, num_caixas, &estoque);

    // Liberar memória
    liberar_estoque(&estoque);
    liberar_caixas(caixas, num_caixas);

    return 0;
}
