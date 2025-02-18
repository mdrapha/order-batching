# Order Picking Optimization using GRASP and ILS

Este repositório contém a implementação de uma abordagem multi-objetiva baseada em **GRASP** (Greedy Randomized Adaptive Search Procedure) e **ILS** (Iterated Local Search) para a otimização do order picking, com foco em restrições adaptativas de peças por onda.

## Sumário

- [Introdução](#introdução)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Pré-Requisitos e Dependências](#pré-requisitos-e-dependências)
- [Autores](#autores)
- [Licença](#licença)

---

## Introdução

A separação de pedidos (order picking) é uma etapa fundamental na cadeia de suprimentos, impactando diretamente nos custos operacionais e prazos de entrega. Este projeto explora uma estratégia de agrupamento de caixas em ondas (batches) considerando restrições de estoque e capacidade máxima de peças por onda. A metodologia combina:

1. **Alocação Inicial Gulosa:** Para atribuir SKUs às caixas, garantindo que cada caixa receba a quantidade necessária de peças.
2. **Refinamento via ILS:** Aplica perturbações controladas e busca local para melhorar a solução inicial, reduzindo a área de alocação.
3. **Agrupamento com GRASP:** Agrupa as caixas em ondas, respeitando um limite adaptativo \(C'\) (menor ou igual a 6000 peças) para balancear a carga e otimizar a logística.

## Pré-Requisitos e Dependências

- **Python 3.8+** (ou versão superior).
- Bibliotecas recomendadas:
  - `pandas` para manipulação de dados.
  - `numpy` para operações numéricas.
  - `matplotlib` ou `seaborn` para geração de gráficos (opcional).
  - Outras bibliotecas conforme especificado em `requirements.txt`.

Para instalar as dependências, execute:
```bash
pip install -r requirements.txt


## Autores
Davi Seiji Kawai dos Santos <davi.seiji@unifesp.br>
Enzo Reis de Oliveira <enzo.oliveira@unifesp.br>
Juan Marcos Martins <juan.martins@unifesp.br>
Marco Antonio Coral dos Santos <macsantos23@unifesp.br>
Raphael Damasceno Rocha de Moraes <raphael.damasceno@unifesp.br>
Sávio Augusto Machado Araujo <savio.augusto@unifesp.br>
