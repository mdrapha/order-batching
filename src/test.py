from database import SQLiteDB
import pandas as pd
import time

db = SQLiteDB()
db.connect()

res = db.query(f"""
    SELECT SUM(PECAS) 
    FROM caixas
    WHERE SKU = 'SKU_21830'""")
print(f"Quantidade de SKU_21830 em pedidos: {res[0][0]}")

res = db.query(f"""
    SELECT SUM(PECAS) 
    FROM estoque
    WHERE SKU = 'SKU_21830'""")
print(f"Quantidade de SKU_21830 no estoque: {res[0][0]}")

db.close()