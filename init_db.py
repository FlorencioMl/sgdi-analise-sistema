import sqlite3
import hashlib

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

conn = sqlite3.connect('demandas.db')
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS api_tokens")
cursor.execute("DROP TABLE IF EXISTS comentarios")
cursor.execute("DROP TABLE IF EXISTS demandas")
cursor.execute("DROP TABLE IF EXISTS usuarios")

cursor.execute("""
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE,
    senha TEXT
)
""")

cursor.execute("""
CREATE TABLE demandas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT,
    descricao TEXT,
    solicitante TEXT,
    data_criacao TEXT,
    prioridade TEXT
)
""")

cursor.execute("""
CREATE TABLE comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id INTEGER,
    comentario TEXT,
    autor TEXT,
    data TEXT,
    FOREIGN KEY (demanda_id) REFERENCES demandas(id)
)
""")

cursor.execute("""
CREATE TABLE api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    token TEXT UNIQUE,
    criado_em TEXT,
    ativo INTEGER DEFAULT 1,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
)
""")

# Senhas agora armazenadas como SHA-256
usuarios = [
    ('admin',         hash_senha('123')),
    ('João Silva',    hash_senha('123')),
    ('Maria Santos',  hash_senha('123')),
    ('Pedro Costa',   hash_senha('123')),
]

cursor.executemany("INSERT INTO usuarios (nome, senha) VALUES (?, ?)", usuarios)

conn.commit()
conn.close()

print("Banco criado com sucesso!")
print("Senhas armazenadas como SHA-256.")
print("Tabela api_tokens criada.")
