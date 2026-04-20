import sqlite3

conn = sqlite3.connect('demandas.db')
cursor = conn.cursor()

cursor.execute("UPDATE demandas SET prioridade = 'Media' WHERE prioridade = 'Alta'")
cursor.execute("UPDATE demandas SET prioridade = 'Alta' WHERE prioridade = 'Critica'")

conn.commit()
conn.close()

print("Prioridades atualizadas com sucesso!")