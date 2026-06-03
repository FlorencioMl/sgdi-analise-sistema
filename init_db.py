import sqlite3
import hashlib

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

conn = sqlite3.connect('demandas.db')
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS logs")
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

cursor.execute("""
CREATE TABLE logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER,
    usuario_nome TEXT,
    acao        TEXT NOT NULL,
    entidade    TEXT,
    entidade_id INTEGER,
    detalhe     TEXT,
    ip          TEXT,
    user_agent  TEXT,
    origem      TEXT DEFAULT 'web',
    criado_em   TEXT NOT NULL
)
""")

# Índices para consultas de auditoria
cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_acao     ON logs(acao)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_usuario  ON logs(usuario_nome)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_criado   ON logs(criado_em)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_entidade ON logs(entidade, entidade_id)")

usuarios = [
    ('admin',        hash_senha('123')),
    ('João Silva',   hash_senha('123')),
    ('Maria Santos', hash_senha('123')),
    ('Pedro Costa',  hash_senha('123')),
]

cursor.executemany("INSERT INTO usuarios (nome, senha) VALUES (?, ?)", usuarios)

conn.commit()
conn.close()

print("Banco criado com sucesso!")
print("Tabelas: usuarios, demandas, comentarios, api_tokens, logs")
print("Índices de auditoria criados.")
