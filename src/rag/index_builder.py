import chromadb
from typing import List

from ..embeddings.base import Embedder
from ..rag.chunking import chunk_text
from ..nps_articles import fetch_articles_for_park


def build_vector_index_for_park(park_code: str, embedder: Embedder):
    """
    Build (or rebuild) a persistent ChromaDB index for a park:
    - Fetch all NPS articles
    - Chunk their text
    - Embed each chunk
    - Store in Chroma vector DB
    """
    articles = fetch_articles_for_park(park_code)

    client = chromadb.PersistentClient(path="chroma_db")
    collection = client.get_or_create_collection(
        name=f"park_{park_code}",
        metadata={"hnsw:space": "cosine"},
    )

    ids: List[str] = []
    docs: List[str] = []
    metas: List[dict] = []

    for article in articles:
        title = article.get("title", "")
        url = article.get("url", "")
        body = (
            article.get("listingDescription", "")
            or article.get("description", "")
            or ""
        )

        if not body.strip():
            continue

        chunks = chunk_text(body)

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{article['id']}_{idx}"
            ids.append(chunk_id)
            docs.append(chunk)
            metas.append(
                {
                    "park_code": park_code,
                    "article_id": article["id"],
                    "title": title,
                    "url": url,
                    "chunk_index": idx,
                }
            )

    if not docs:
        print(f"No article content found for park {park_code}. Nothing to index.")
        return collection

    embeddings = embedder.embed_texts(docs)

    collection.add(
        ids=ids,
        documents=docs,
        metadatas=metas,
        embeddings=embeddings,
    )

    return collection
