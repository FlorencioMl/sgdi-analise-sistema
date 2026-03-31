import sqlite3

conn = sqlite3.connect('demandas.db')
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS demandas")

cursor.execute('''
CREATE TABLE demandas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT,
    descricao TEXT,
    solicitante TEXT,
    data_criacao TEXT,
    prioridade TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id INTEGER,
    comentario TEXT,
    autor TEXT,
    data TEXT
)
''')

cursor.execute("""
INSERT INTO demandas (titulo, descricao, solicitante, data_criacao, prioridade)
VALUES ('Corrigir bug no login', 'Usuários não conseguem fazer login', 'João Silva', '2024-01-15 10:30:00', 'Critica')
""")

cursor.execute("""
INSERT INTO demandas (titulo, descricao, solicitante, data_criacao, prioridade)
VALUES ('Implementar relatório de vendas', 'Precisamos de um relatório mensal', 'Maria Santos', '2024-01-16 14:20:00', 'Alta')
""")

cursor.execute("""
INSERT INTO demandas (titulo, descricao, solicitante, data_criacao, prioridade)
VALUES ('Melhorar performance', 'Sistema está lento', 'Pedro Costa', '2024-01-17 09:15:00', 'Baixa')
""")

cursor.execute("""
INSERT INTO demandas (titulo, descricao, solicitante, data_criacao, prioridade)
VALUES ('Adicionar filtros', 'Usuários querem filtrar demandas', 'Ana Lima', '2024-01-18 11:00:00', 'Alta')
""")

cursor.execute("""
INSERT INTO comentarios (demanda_id, comentario, autor, data)
VALUES (1, 'Vou investigar esse bug', 'Tech Team', '2024-01-15 11:00:00')
""")

cursor.execute("""
INSERT INTO comentarios (demanda_id, comentario, autor, data)
VALUES (1, 'Bug corrigido na branch develop', 'Desenvolvedor', '2024-01-15 16:30:00')
""")

conn.commit()
conn.close()

print("Banco recriado com sucesso!")