import pytest
from produto import Produto
from caixa import Caixa
from onda import Onda
from estoque import Estoque

def test_add_produto():

    sku = "SKU_1"
    qtd = 100
    sku = int(sku.split('_')[1])

    produto = Produto(sku, qtd)

    assert produto.get_sku() == 1
    assert produto.get_qtd() == 100

def test_set_qtd():

    sku = "SKU_1"
    qtd = 100
    sku = int(sku.split('_')[1])

    produto = Produto(sku, qtd)

    produto.set_qtd(200)

    assert produto.get_qtd() == 200
    
def test_create_caixa():

    id_caixa = 1
    classe_onda = 1
    id_onda = 1

    caixa = Caixa(id_caixa, classe_onda, id_onda)

    assert caixa.get_classe_onda() == 1
    assert caixa.get_id_onda() == 1

def test_add_produto_caixa():

    id_caixa = 1
    classe_onda = 1
    id_onda = 1

    caixa = Caixa(id_caixa, classe_onda, id_onda)

    sku = "SKU_1"
    qtd = 100
    sku = int(sku.split('_')[1])

    produto = Produto(sku, qtd)

    caixa.add_produto(produto)

    assert len(caixa.get_produtos()) == 1
    assert caixa.get_total_itens() == 100
    assert caixa.get_produtos()[0].get_sku() == 1

def test_remove_produto_caixa():

    id_caixa = 1
    classe_onda = 1
    id_onda = 1

    caixa = Caixa(id_caixa, classe_onda, id_onda)

    sku = "SKU_1"
    qtd = 100
    sku = int(sku.split('_')[1])

    produto = Produto(sku, qtd)

    caixa.add_produto(produto)

    caixa.remove_produto(produto)

    assert len(caixa.get_produtos()) == 0
    assert caixa.get_total_itens() == 0

def test_create_estoque():

    andar = 1
    corredor = 5

    sku = "SKU_123"
    qtd = 145
    sku = int(sku.split('_')[1])

    produto = Produto(sku, qtd)

    estoque = Estoque(andar, corredor, produto, qtd)

    assert estoque.get_andar() == 1
    assert estoque.get_corredor() == 5
    assert estoque.get_produto_sku() == 123
    assert estoque.get_qtd() == 145

def test_mudar_qtd_estoque():
    
    andar = 1
    corredor = 5

    sku = "SKU_123"
    qtd = 145
    sku = int(sku.split('_')[1])

    produto = Produto(sku, qtd)

    estoque = Estoque(andar, corredor, produto, qtd)

    estoque.mudar_qtd(10)

    assert estoque.get_qtd() == 155

def test_create_onda():

    id_onda = 1

    onda = Onda([], id_onda)

    assert onda.get_id() == 1

def test_add_caixa_onda():

    id_onda = 1

    onda = Onda([], id_onda)

    id_caixa = 1
    classe_onda = 1
    id_onda = 1

    caixa = Caixa(id_caixa, classe_onda, id_onda)

    onda.add_caixa(caixa)

    assert len(onda.get_caixas()) == 1

def test_remove_caixa_onda():
    
    id_onda = 1

    onda = Onda([], id_onda)

    id_caixa = 1
    classe_onda = 1
    id_onda = 1

    caixa = Caixa(id_caixa, classe_onda, id_onda)

    onda.add_caixa(caixa)

    onda.remove_caixa(caixa)

    assert len(onda.get_caixas()) == 0

def test_add_produto_onda():

    id_onda = 1

    onda = Onda([], id_onda)

    id_caixa = 1
    classe_onda = 1
    id_onda = 1

    caixa = Caixa(id_caixa, classe_onda, id_onda)

    sku = "SKU_1"
    qtd = 100
    sku = int(sku.split('_')[1])

    produto = Produto(sku, qtd)

    caixa.add_produto(produto)

    onda.add_caixa(caixa)

    assert onda.get_total_itens() == 100