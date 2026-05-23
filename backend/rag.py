import voyageai
from qdrant_client import QdrantClient
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
QDRANT_PATH = os.getenv("QDRANT_PATH")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "qarar_islamic_corpus_voyage")
EMBEDDING_MODEL = os.getenv("VOYAGE_MODEL", "voyage-multilingual-2")

# Classical Arabic synonyms — books use different words than modern Arabic
QUERY_EXPANSIONS = {
    "وحدة": "وحدة عزلة وحشة انفراد غربة استيحاش",
    "حزن": "حزن هم غم كآبة حسرة أسى",
    "قلق": "قلق خوف هم وسواس اضطراب فزع",
    "اكتئاب": "اكتئاب حزن كآبة انقباض ضيق صدر",
    "غضب": "غضب سخط انفعال حدة طيش",
    "ذنب": "ذنب معصية خطيئة توبة ندم استغفار",
    "يأس": "يأس قنوط إحباط ضعف رجاء",
    "خوف": "خوف قلق وسواس هلع فزع",
    "ضغط": "ضغط إجهاد تعب إرهاق",
    "وسواس": "وسواس شيطان خواطر هواجس",
    "فشل": "فشل خيبة إحباط يأس ابتلاء",
    "خيانة": "خيانة ظلم جور غدر",
    "صبر": "صبر ثبات احتساب تحمل",
    "توبة": "توبة استغفار رجوع إنابة",
    "loneliness": "وحدة عزلة وحشة انفراد",
    "anxiety": "قلق خوف وسواس اضطراب",
    "depression": "اكتئاب حزن كآبة انقباض",
    "grief": "حزن هم غم أسى حسرة",
    "guilt": "ذنب معصية ندم استغفار",
}

_voyage_client = None
_qdrant_client = None


def get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        _voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    return _voyage_client


def get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        if url and api_key:
            _qdrant_client = QdrantClient(url=url, api_key=api_key)
        else:
            path = os.getenv("QDRANT_PATH", r"C:\Users\faisa\Downloads\Qarar\Qdrant_DB_New")
            _qdrant_client = QdrantClient(path=path)
    return _qdrant_client


def expand_query(query: str) -> str:
    """Add classical Arabic synonyms to improve search recall"""
    query_lower = query.lower()
    for keyword, expansion in QUERY_EXPANSIONS.items():
        if keyword in query or keyword in query_lower:
            return f"{query} {expansion}"
    return query


async def search_knowledge_base(query: str, top_k: int = 5) -> List[dict]:
    """
    Search the Islamic books vector database.
    Returns passages from Ibn al-Qayyim, Al-Ghazali, Ibn al-Jawzi, etc.
    """
    try:
        vo = get_voyage_client()
        qdrant = get_qdrant_client()

        expanded = expand_query(query)

        embedding = vo.embed(
            [expanded],
            model=EMBEDDING_MODEL,
            input_type="query"
        ).embeddings[0]

        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            limit=top_k,
        ).points

        formatted = []
        for r in results:
            p = r.payload
            formatted.append({
                "book": p.get("book", ""),
                "author": p.get("author", ""),
                "text": p.get("text", ""),
                "score": round(r.score, 4)
            })

        # Filter by relevance threshold
        filtered = [r for r in formatted if r["score"] >= 0.3]
        return filtered if filtered else formatted[:2]

    except Exception as e:
        print(f"[RAG] search error: {e}")
        return []
