from produto import Produto

class Estoque:

    def __init__(self, andar, corredor):
        self.produtos = []
        self.andar = andar
        self.corredor = corredor

    def add_produto(self, produto: Produto):
        self.produtos.append(produto)

    def remove_produto(self, produto: Produto):
        self.produtos.remove(produto)

    def get_produtos(self):
        return self.produtos
    
    def get_andar(self):
        return self.andar
    
    def get_corredor(self):
        return self.corredor

    def get_total_itens(self):
        total = 0
        for produto in self.produtos:
            total += produto.get_qtd()
        return total
        