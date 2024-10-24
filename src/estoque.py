from produto import Produto

class Estoque:

    def __init__(self, andar, corredor, produto: Produto, qtd):
        self.andar = andar
        self.corredor = corredor
        self.produto = produto
        self.qtd = qtd
    
    def get_andar(self):
        return self.andar
    
    def get_corredor(self):
        return self.corredor
    
    def get_produto_sku(self):
        return self.produto.get_sku()
    
    def mudar_qtd(self, dif):
        self.qtd += dif

    def get_qtd(self):
        return self.qtd
        