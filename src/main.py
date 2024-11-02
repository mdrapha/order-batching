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

caixas_real = pd.read_sql_query("SELECT * FROM caixas", db.conn)
estoque_real = pd.read_sql_query("SELECT * FROM estoque", db.conn)
caixas_real.to_sql("caixas_real", db.conn, if_exists="replace", index=False)
estoque_real.to_sql("estoque_real", db.conn, if_exists="replace", index=False)

i = 1
print(f"Iniciando iterações...")
while True:
    time_start = time.time()
    
    cmd = f"""
    WITH ranked_caixas AS (
        SELECT 
            caixas_real.CAIXA_ID, 
            estoque_real.ANDAR, 
            estoque_real.CORREDOR,
            caixas_real.SKU,
            caixas_real.PECAS,
            ROW_NUMBER() OVER (
                PARTITION BY caixas_real.SKU, caixas_real.CAIXA_ID
                ORDER BY estoque_real.ANDAR ASC, estoque_real.CORREDOR ASC
            ) AS rn
        FROM caixas_real
        JOIN estoque_real 
        ON caixas_real.SKU = estoque_real.SKU
        AND caixas_real.PECAS <= estoque_real.PECAS
        WHERE caixas_real.PECAS <= estoque_real.PECAS)
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
    caixas_picking = pd.read_sql_query(cmd, db.conn)
    caixas_picking.to_sql("caixas_picking", db.conn, if_exists="replace", index=False)
    # print(caixas_picking)

    cmd = f"""
        WITH caixas_info AS (
            SELECT 
                CAIXA_ID, 
                COUNT(SKU) AS SKUS, 
                SUM(PECAS) AS PECAS,
                COUNT(DISTINCT ANDAR) AS ANDARES
            FROM caixas_picking
            GROUP BY CAIXA_ID
        )
        SELECT 
            caixas_picking.CAIXA_ID, 
            caixas_picking.ANDAR, 
            caixas_picking.CORREDOR,
            caixas_picking.SKU, 
            caixas_picking.PECAS
        FROM caixas_picking
        JOIN caixas_info
            ON caixas_picking.CAIXA_ID = caixas_info.CAIXA_ID
        ORDER BY 
            caixas_info.ANDARES ASC,
            caixas_info.PECAS ASC, 
            caixas_picking.ANDAR ASC,
            caixas_picking.CORREDOR ASC""" # parâmetros de priorização de caixas no ORDER BY
    caixas_picking = pd.read_sql_query(cmd, db.conn)
    caixas_picking.to_sql("caixas_picking", db.conn, if_exists="replace", index=False)
    # print(caixas_picking)

    for caixa, andar, corredor, sku, qtd_pecas in caixas_picking.values:
        cmd = f"""
            UPDATE estoque_real
            SET PECAS = PECAS - {qtd_pecas}
            WHERE SKU = '{sku}' 
            AND ANDAR = {andar}
            AND CORREDOR = {corredor}
            AND PECAS >= {qtd_pecas}"""
        rows = db.query(cmd)
        if rows > 0:
            cmd = f"""
                UPDATE caixas_real
                SET PECAS = PECAS - {qtd_pecas}
                WHERE CAIXA_ID = {caixa}
                AND SKU = '{sku}'"""
            db.query(cmd)   
    
    cmd = f"""
        DELETE FROM estoque_real
        WHERE PECAS = 0"""
    db.query(cmd)
    
    cmd = f"""
        DELETE FROM caixas_real
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
    FROM caixas_real"""
res = db.query(cmd)
print(f"Pedidos restantes: {res[0][0]}")

db.close()