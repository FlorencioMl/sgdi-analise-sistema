import sqlite3


conn = sqlite3.connect('demandas.db')
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS comentarios")
cursor.execute("DROP TABLE IF EXISTS demandas")
cursor.execute("DROP TABLE IF EXISTS usuarios")


cursor.execute("""
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL
)
""")


cursor.execute("""
CREATE TABLE demandas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    solicitante TEXT NOT NULL,
    data_criacao TEXT NOT NULL,
    prioridade TEXT NOT NULL
)
""")


cursor.execute("""
CREATE TABLE comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id INTEGER,
    comentario TEXT,
    autor TEXT,
    data TEXT
)
""")

usuarios = [
    ('admin', '123'),
    ('João Silva', '123'),
    ('Maria Santos', '123'),
    ('Pedro Costa', '123'),
    ('Ana Lima', '123')
]

cursor.executemany(
    "INSERT INTO usuarios (nome, senha) VALUES (?, ?)",
    usuarios
)

demandas = [
    (
        'Corrigir bug no login',
        'Usuários não conseguem fazer login',
        'João Silva',
        '2024-01-15 10:30:00',
        'Alta'
    ),
    (
        'Implementar relatório de vendas',
        'Precisamos de um relatório mensal',
        'Maria Santos',
        '2024-01-16 14:20:00',
        'Alta'
    ),
    (
        'Melhorar performance',
        'Sistema está lento',
        'Pedro Costa',
        '2024-01-17 09:15:00',
        'Baixa'
    ),
    (
        'Adicionar filtros',
        'Usuários querem filtrar demandas',
        'Ana Lima',
        '2024-01-18 11:00:00',
        'Alta'
    )
]

cursor.executemany("""
INSERT INTO demandas
(titulo, descricao, solicitante, data_criacao, prioridade)
VALUES (?, ?, ?, ?, ?)
""", demandas)


comentarios = [
    (
        1,
        'Vou investigar esse bug',
        'Tech Team',
        '2024-01-15 11:00:00'
    ),
    (
        1,
        'Bug corrigido na branch develop',
        'Desenvolvedor',
        '2024-01-15 16:30:00'
    )
]

cursor.executemany("""
INSERT INTO comentarios
(demanda_id, comentario, autor, data)
VALUES (?, ?, ?, ?)
""", comentarios)


conn.commit()
conn.close()

print("Banco recriado com sucesso!")