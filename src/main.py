from database import SQLiteDB
import pandas as pd
import time

db = SQLiteDB()
db.connect()

caixas = pd.read_csv("data/caixas.csv")
estoque = pd.read_csv("data/estoque.csv")
caixas.to_sql("caixas", db.conn, if_exists="replace", index=False)
estoque.to_sql("estoque", db.conn, if_exists="replace", index=False)
# print(caixas)
# print(estoque)

i = 1
print(f"Iniciando iterações...")
while True:
    time_start = time.time()
    
    cmd = f"""
    WITH ranked_caixas AS (
        SELECT 
            caixas.CAIXA_ID, 
            estoque.ANDAR, 
            estoque.CORREDOR,
            caixas.SKU,
            caixas.PECAS,
            ROW_NUMBER() OVER (
                PARTITION BY caixas.SKU, caixas.CAIXA_ID
                ORDER BY estoque.ANDAR ASC, estoque.CORREDOR ASC
            ) AS rn
        FROM caixas
        JOIN estoque 
        ON caixas.SKU = estoque.SKU
        WHERE caixas.PECAS <= estoque.PECAS)
    SELECT 
        CAIXA_ID, 
        ANDAR, 
        CORREDOR, 
        SKU, 
        PECAS
    FROM 
        ranked_caixas
    WHERE 
        rn = 1;
    """
    picking_temp = pd.read_sql_query(cmd, db.conn)
    picking_temp.to_sql("picking_temp", db.conn, if_exists="replace", index=False)
    # print(picking_temp)

    cmd = f"""
        WITH caixas_info AS (
            SELECT 
                CAIXA_ID, 
                COUNT(SKU) AS SKUS, 
                SUM(PECAS) AS PECAS,
                COUNT(DISTINCT ANDAR) AS ANDARES
            FROM picking_temp
            GROUP BY CAIXA_ID
        )
        SELECT 
            picking_temp.CAIXA_ID, 
            picking_temp.ANDAR, 
            picking_temp.CORREDOR,
            picking_temp.SKU, 
            picking_temp.PECAS
        FROM picking_temp
        JOIN caixas_info
            ON picking_temp.CAIXA_ID = caixas_info.CAIXA_ID
        ORDER BY 
            caixas_info.ANDARES ASC,
            caixas_info.PECAS ASC, 
            caixas_info.SKUS ASC,
            picking_temp.ANDAR ASC,
            picking_temp.CORREDOR ASC""" # parâmetros de priorização de caixas no ORDER BY
    picking_temp = pd.read_sql_query(cmd, db.conn)
    picking_temp.to_sql("picking_temp", db.conn, if_exists="replace", index=False)
    # print(picking_temp)

    for caixa, andar, corredor, sku, qtd_pecas in picking_temp.values:
        cmd = f"""
            UPDATE estoque
            SET PECAS = PECAS - {qtd_pecas}
            WHERE SKU = '{sku}' 
            AND ANDAR = {andar}
            AND CORREDOR = {corredor}
            AND PECAS >= {qtd_pecas}"""
        rows = db.query(cmd)
        if rows > 0:
            cmd = f"""
                UPDATE caixas
                SET PECAS = PECAS - {qtd_pecas}
                WHERE CAIXA_ID = {caixa}
                AND SKU = '{sku}'"""
            db.query(cmd)   
            
    cmd = f"""
        SELECT 
            picking_temp.CAIXA_ID, 
            picking_temp.ANDAR, 
            picking_temp.CORREDOR, 
            picking_temp.SKU, 
            picking_temp.PECAS
        FROM picking_temp
        JOIN caixas
        ON picking_temp.CAIXA_ID = caixas.CAIXA_ID
        AND picking_temp.SKU = caixas.SKU
        WHERE caixas.PECAS = 0"""
    picking = pd.read_sql_query(cmd, db.conn)
    picking.to_sql("picking", db.conn, if_exists="append", index=False)
    
    cmd = f"""
        DELETE FROM estoque
        WHERE PECAS = 0"""
    db.query(cmd)
    
    cmd = f"""
        DELETE FROM caixas
        WHERE PECAS = 0"""
    rows = db.query(cmd)
    
    if rows == 0 or i == 20:
        break
    
    print(f"Pedidos processados: {rows}")
    min, sec = divmod(time.time() - time_start, 60)
    print(f"Iteração {i} executada em {int(min)}m{int(sec)}s\n")
    i += 1 
    
cmd = f"""
    SELECT COUNT(*)
    FROM caixas"""
res = db.query(cmd)
print(f"Pedidos restantes: {res[0][0]}")

db.close()