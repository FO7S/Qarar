import sqlite3

db = r'C:\Users\faisa\Downloads\Qarar\Qdrant_DB_Voyage\collection\qarar_islamic_corpus_voyage\storage.sqlite'
conn = sqlite3.connect(db)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', cursor.fetchall())

cursor.execute("SELECT * FROM sqlite_master")
for row in cursor.fetchall():
    print(row)

conn.close()