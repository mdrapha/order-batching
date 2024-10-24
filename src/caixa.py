from produto import Produto

class Caixa:

    def __init__(self, id_caixa, classe_onda, id_onda):
        self.produtos = []
        self.id_caixa = id_caixa
        self.classe_onda = classe_onda
        self.id_onda = id_onda

    def add_produto(self, produto: Produto):
        self.produtos.append(produto)
        print(f'Produto {produto.get_sku()} adicionado na caixa {self.id_onda}')

    def remove_produto(self, produto: Produto):
        self.produtos.remove(produto)
        print(f'Produto {produto.get_sku()} removido da caixa {self.id_onda}')
    
    def get_produtos(self):
        return self.produtos
    
    def get_classe_onda(self):
        return self.classe_onda
    
    def get_id_onda(self):
        return self.id_onda

    def set_onda(self, new_onda):
        self.onda = new_onda
        