import sqlite3

class SQLiteDB:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SQLiteDB, cls).__new__(cls)
            cls._instance.conn = None
        return cls._instance

    def connect(self):
        if not self.conn:
            try:
                self.conn = sqlite3.connect("data/database.db")
                self.conn.execute('PRAGMA foreign_keys = ON')
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"Erro ao conectar ao banco de dados: {e}")
                
    def query(self, query, values=None):
        try:
            cursor = self.conn.cursor()
            if values:
                cursor.execute(query, values)
            else:
                cursor.execute(query)
            self.conn.commit()
            if query.strip().upper().startswith("SELECT"):
                return cursor.fetchall()
            else:
                return cursor.rowcount
        except sqlite3.Error as e:
            print(f"Erro ao executar query: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None