"""
Migration script: Local Qdrant → Qdrant Cloud
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

LOCAL_PATH = r"C:\Users\faisa\Downloads\Qarar\Qdrant_DB_New"
CLOUD_URL = "https://c9631344-ee45-41ec-bc60-f39dd6c6bae9.eu-west-1-0.aws.cloud.qdrant.io"
CLOUD_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MjUzOTQwZTQtNGZiZi00ZTA1LWEwOTMtY2IwNDlhODAzM2NiIn0.HVDTpcGKZcuJMlAOoRCLn1iYvy4cRfYyYeaQlYfe_Uo"
COLLECTION = "qarar_islamic_corpus_voyage"
BATCH_SIZE = 100

print("Connecting to local Qdrant...")
local = QdrantClient(path=LOCAL_PATH)

print("Connecting to Qdrant Cloud...")
cloud = QdrantClient(url=CLOUD_URL, api_key=CLOUD_API_KEY)

existing = [c.name for c in cloud.get_collections().collections]
if COLLECTION in existing:
    print("Collection exists — deleting...")
    cloud.delete_collection(COLLECTION)

print("Creating collection on cloud...")
cloud.create_collection(
    collection_name=COLLECTION,
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)

local_info = local.get_collection(COLLECTION)
total = local_info.points_count
print(f"Total vectors to migrate: {total}")

offset = None

with tqdm(total=total, desc="Migrating") as pbar:
    while True:
        results, next_offset = local.scroll(
            collection_name=COLLECTION,
            limit=BATCH_SIZE,
            offset=offset,
            with_vectors=True,
            with_payload=True
        )

        if not results:
            break

        points = [
            PointStruct(
                id=str(point.id),
                vector=point.vector,
                payload=point.payload
            )
            for point in results
        ]

        cloud.upsert(collection_name=COLLECTION, points=points)
        pbar.update(len(results))

        if next_offset is None:
            break
        offset = next_offset

cloud_info = cloud.get_collection(COLLECTION)
print(f"\n✅ Done!")
print(f"Local:  {total}")
print(f"Cloud:  {cloud_info.points_count}")
print(f"\nUpdate .env:")
print(f"QDRANT_URL={CLOUD_URL}")
print(f"QDRANT_API_KEY={CLOUD_API_KEY}")