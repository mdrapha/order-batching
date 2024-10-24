class Produto:

    def __init__(self, sku, qtd):
        self.sku = sku
        self.qtd = qtd

    def get_sku(self):
        return self.sku

    def get_qtd(self):
        return self.qtd

    def set_qtd(self, new_qtd):
        self.preco = new_qtd