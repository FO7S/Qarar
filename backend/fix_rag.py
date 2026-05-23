import sqlite3
import pickle
import json

db = r'C:\Users\faisa\Downloads\Qarar\Qdrant_DB_Voyage\collection\qarar_islamic_corpus_voyage\storage.sqlite'
conn = sqlite3.connect(db)
cursor = conn.cursor()

cursor.execute("SELECT id, point FROM points LIMIT 1")
row = cursor.fetchone()
print("ID:", row[0])

# Try to deserialize the blob
blob = row[1]
print("Blob size:", len(blob))
print("Blob start:", blob[:20])

conn.close()