import chromadb
from typing import List, Dict, Any

from ..embeddings.base import Embedder
from ..rag.chunking import chunk_text
from ..nps_articles import fetch_articles_for_park
from ..nps_things_to_do import get_things_to_do_for_park


def _build_article_docs(park_code: str) -> Dict[str, List[Any]]:
    """
    Fetch NPS articles and turn them into documents + metadata suitable for Chroma.
    Returns a dict with ids, docs, metas lists.
    """
    articles = fetch_articles_for_park(park_code)

    ids: List[str] = []
    docs: List[str] = []
    metas: List[dict] = []

    for article in articles:
        article_id = article.get("id", "")
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
            chunk_id = f"article_{article_id}_{idx}"
            ids.append(chunk_id)
            docs.append(chunk)
            metas.append(
                {
                    "source": "nps_article",
                    "park_code": park_code,
                    "article_id": article_id,
                    "title": title,
                    "url": url,
                    "chunk_index": idx,
                }
            )

    return {"ids": ids, "docs": docs, "metas": metas}


def _build_things_to_do_docs(park_code: str) -> Dict[str, List[Any]]:
    """
    Fetch NPS ThingsToDo items and turn them into documents + metadata.

    Each item becomes a single, rich text document that plays nicely with RAG,
    especially for trail/hike recommendations.
    """
    things = get_things_to_do_for_park(park_code)

    ids: List[str] = []
    docs: List[str] = []
    metas: List[dict] = []

    for idx, item in enumerate(things):
        # Build a descriptive text blob for embedding
        parts: List[str] = [
            f"Title: {item.title}",
            f"Park: {item.park_code}",
        ]

        # Prefer long_description as the main body
        if item.long_description:
            parts.append(f"Details: {item.long_description}")
        elif item.listing_description:
            parts.append(f"Details: {item.listing_description}")
        elif item.short_description:
            parts.append(f"Short description: {item.short_description}")

        if item.activities:
            parts.append("Activities: " + ", ".join(item.activities))
        if item.duration_hours is not None:
            parts.append(f"Typical duration: ~{item.duration_hours:.1f} hours")
        if item.url:
            parts.append(f"More info: {item.url}")

        if item.is_trail:
            parts.append("Type: trail / hike")
        else:
            parts.append("Type: other activity")

        text = "\n".join(parts)

        doc_id = f"thing_{item.id}"
        ids.append(doc_id)
        docs.append(text)

        # Metadata must be scalar only; no None, no lists
        activities_str = ", ".join(item.activities) if item.activities else ""
        duration_val = float(item.duration_hours) if item.duration_hours is not None else -1.0

        metas.append(
            {
                "source": "nps_things_to_do",
                "park_code": park_code,
                "thing_id": item.id,
                "title": item.title,
                "url": item.url,
                "activities": activities_str,
                "duration_hours": duration_val,
                "is_trail": bool(item.is_trail),
                "chunk_index": 0,
            }
        )

    return {"ids": ids, "docs": docs, "metas": metas}


def build_vector_index_for_park(park_code: str, embedder: Embedder):
    """
    Build (or rebuild) a persistent ChromaDB index for a park:

    - Fetch all NPS articles  → chunk → embed → store
    - Fetch NPS ThingsToDo    → 1 doc per item → embed → store

    Everything goes into the same Chroma collection: park_{park_code},
    with a 'source' field in metadata to distinguish content types.
    """
    client = chromadb.PersistentClient(path="chroma_db")
    collection = client.get_or_create_collection(
        name=f"park_{park_code}",
        metadata={"hnsw:space": "cosine"},
    )

    # Optional: clear existing docs if you want a clean rebuild
    # collection.delete(where={})

    article_data = _build_article_docs(park_code)
    things_data = _build_things_to_do_docs(park_code)

    ids: List[str] = article_data["ids"] + things_data["ids"]
    docs: List[str] = article_data["docs"] + things_data["docs"]
    metas: List[dict] = article_data["metas"] + things_data["metas"]

    if not docs:
        print(f"No content (articles or things-to-do) found for park {park_code}. Nothing to index.")
        return collection

    embeddings = embedder.embed_texts(docs)

    collection.add(
        ids=ids,
        documents=docs,
        metadatas=metas,
        embeddings=embeddings,
    )

    return collection
