import chromadb
from typing import List, Tuple

from ..models import DocumentChunk
from ..embeddings.base import Embedder


class RAGRetriever:
    def __init__(self, park_code: str, embedder: Embedder):
        self.park_code = park_code
        self.embedder = embedder

        self.client = chromadb.PersistentClient(path="chroma_db")
        self.collection = self.client.get_collection(name=f"park_{park_code}")

    def search(self, query: str, top_k: int = 3) -> List[Tuple[DocumentChunk, float]]:
        """
        Return (DocumentChunk, score) for the top_k most relevant chunks.
        """
        query_emb = self.embedder.embed_text(query)

        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            where={"park_code": self.park_code},
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        out: List[Tuple[DocumentChunk, float]] = []

        for doc, meta, dist in zip(docs, metas, dists):
            chunk = DocumentChunk(
                doc_id=str(meta.get("article_id", "")),
                chunk_id=int(meta.get("chunk_index", 0)),
                text=doc,
                source=meta.get("url", ""),
            )
            out.append((chunk, float(dist)))

        return out
