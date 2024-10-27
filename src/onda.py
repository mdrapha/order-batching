from caixa import Caixa

class Onda:

    def __init__(self, caixas, id):
        self.caixas = []
        self.id = id

    def add_caixa(self, caixa: Caixa):
        self.caixas.append(caixa)

    def remove_caixa(self, caixa: Caixa):
        self.caixas.remove(caixa)

    def get_caixas(self):
        return self.caixas

    def get_id(self):
        return self.id
    
    def set_id(self, new_id):
        self.id = new_id

    def get_total_itens(self):
        total = 0
        for caixa in self.caixas:
            total += caixa.get_total_itens()
        return total
        