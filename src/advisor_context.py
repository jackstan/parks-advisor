from typing import List, Dict, Any

from .rag.index_builder import build_vector_index_for_park
from .models import TripRequest, Scores, Alert, DocumentChunk, WeatherDay
from .weather_client import get_weather_for_trip
from .nps_client import get_alerts_for_park
from .scoring import compute_scores
from .embeddings.local_embedder import LocalEmbedder
from .rag.retriever import RAGRetriever


def build_trip_context(trip: TripRequest) -> Dict[str, Any]:
    """
    Orchestrate all data sources and return a rich context dict:
    - trip info
    - weather
    - scores + risk flags + notes
    - alerts
    - retrieved RAG chunks

    This is what the LLM layer will consume.
    """

    # 1) Core signals: weather + alerts + scores
    weather_days: List[WeatherDay] = get_weather_for_trip(
        trip.park_code, trip.start_date, trip.end_date
    )
    alerts: List[Alert] = get_alerts_for_park(trip.park_code)

    print(f"[DEBUG] get_alerts_for_park('{trip.park_code}') returned {len(alerts)} alerts")

    scores: Scores = compute_scores(trip, weather_days, alerts)

    # 2) Build RAG queries based on risk flags / trip type
    queries: List[str] = []

    if "weather_risk" in scores.risk_flags:
        queries.append(
            "weather safety and gear recommendations for hiking in Yosemite"
        )

    if "access_risk" in scores.risk_flags:
        queries.append(
            "Yosemite trail and road closures and how to adapt hiking plans"
        )

    # Always add at least one general planning query
    queries.append("trip planning tips for hiking in Yosemite")

    # 3) Call RAG for top-k chunks across all queries
    embedder = LocalEmbedder()

    # Ensure the vector index for this park exists and is populated
    build_vector_index_for_park(trip.park_code, embedder)

    retriever = RAGRetriever(trip.park_code, embedder)

    rag_chunks: List[DocumentChunk] = []
    for q in queries:
        results = retriever.search(q, top_k=2)
        for chunk, score in results:
            rag_chunks.append(chunk)

    # 4) De-duplicate chunks by (doc_id, chunk_id)
    seen = set()
    unique_chunks: List[DocumentChunk] = []
    for c in rag_chunks:
        key = (c.doc_id, c.chunk_id)
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    return {
        "trip": trip,
        "weather": weather_days,      # 👈 NEW: make weather available to prompt builder
        "scores": scores,
        "alerts": alerts,
        "rag_chunks": unique_chunks,
    }
