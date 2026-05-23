import json
import uuid
import os
from dotenv import load_dotenv
from tqdm import tqdm

import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

load_dotenv()

# ==================== Config ====================
CHUNKS_FILE = r"C:\Users\faisa\Downloads\Qarar\RAG_Output\chunks.jsonl"
NEW_QDRANT_PATH = r"C:\Users\faisa\Downloads\Qarar\Qdrant_DB_New"
COLLECTION = "qarar_islamic_corpus_voyage"
VOYAGE_KEY = os.getenv("VOYAGE_API_KEY", "pa-FBLNEqywdGzqV_IZkPRCpDxOQ7KY_IFb51cK2DsUy_L")
BATCH_SIZE = 64

# ==================== Init ====================
print("Connecting to Voyage AI...")
vo = voyageai.Client(api_key=VOYAGE_KEY)

print(f"Creating Qdrant DB at: {NEW_QDRANT_PATH}")
qdrant = QdrantClient(path=NEW_QDRANT_PATH)

# Delete if exists
if COLLECTION in [c.name for c in qdrant.get_collections().collections]:
    print(f"Deleting existing collection: {COLLECTION}")
    qdrant.delete_collection(COLLECTION)

# Create fresh collection
qdrant.create_collection(
    collection_name=COLLECTION,
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)
print(f"Collection created: {COLLECTION}")

# ==================== Load Chunks ====================
print(f"\nLoading chunks from: {CHUNKS_FILE}")
chunks = []
with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            chunks.append(json.loads(line))

print(f"Total chunks: {len(chunks)}")

# ==================== Embed & Upload ====================
print(f"\nEmbedding and uploading in batches of {BATCH_SIZE}...")

for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Progress"):
    batch = chunks[i:i + BATCH_SIZE]
    texts = [c["text"] for c in batch]

    # Get embeddings from Voyage AI
    embeddings = vo.embed(
        texts,
        model="voyage-multilingual-2",
        input_type="document"
    ).embeddings

    # Build Qdrant points
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, c["chunk_id"])),
            vector=emb,
            payload={
                "chunk_id": c["chunk_id"],
                "book_id": c.get("book_id", ""),
                "book": c.get("book", ""),
                "author": c.get("author", ""),
                "text": c["text"],
                "page_start": c.get("page_start"),
                "page_end": c.get("page_end"),
                "chunk_index": c.get("chunk_index", i),
            }
        )
        for c, emb in zip(batch, embeddings)
    ]

    qdrant.upsert(collection_name=COLLECTION, points=points)

# ==================== Done ====================
total = qdrant.get_collection(COLLECTION).points_count
print(f"\n✅ Done!")
print(f"Collection: {COLLECTION}")
print(f"Total vectors: {total}")
print(f"DB path: {NEW_QDRANT_PATH}")
print(f"\nNext step — update .env:")
print(f"QDRANT_PATH=C:\\Users\\faisa\\Downloads\\Qarar\\Qdrant_DB_New")