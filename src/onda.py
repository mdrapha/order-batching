from src.caixa import Caixa

class Onda:

    def __init__(self, caixas, id):
        self.caixas = []
        self.id = id

    def add_caixa(self, caixa: Caixa):
        self.caixas.append(caixa)
        print(f'Caixa {caixa.get_id()} adicionada na onda {self.id}')

    def remove_caixa(self, caixa: Caixa):
        self.caixas.remove(caixa)
        print(f'Caixa {caixa.get_id()} removida da onda {self.id}')

    def get_caixas(self):
        return self.caixas

    def get_id(self):
        return self.id
    
    def set_id(self, new_id):
        self.id = new_id
        