from typing import List, Dict, Any

from .rag.index_builder import build_vector_index_for_park

from .models import TripRequest, Scores, Alert, WeatherDay, DocumentChunk
from .weather_client import get_weather_for_trip
from .nps_client import get_alerts_for_park
from .scoring import compute_scores
from .embeddings.local_embedder import LocalEmbedder
from .rag.retriever import RAGRetriever


def build_trip_context(trip: TripRequest) -> Dict[str, Any]:
    """
    Orchestrate all data sources and return a rich context dict:
    - trip info
    - weather days
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

    # 2) Build RAG queries based on trip profile, constraints, and risk flags

    queries: List[str] = []

    activity = getattr(trip, "activity_type", "hiking")
    profile = getattr(trip, "hiker_profile", "intermediate")
    constraints = getattr(trip, "constraints", {}) or {}
    max_hours = None
    if isinstance(constraints, dict):
        max_hours = constraints.get("max_hike_hours")

    # --- Primary: trail-focused queries (HIGH weight) ------------------------
    if max_hours is not None:
        trail_query_main = (
            f"recommended {activity} trails in Yosemite National Park for {profile} "
            f"hikers, with trail descriptions and options that take up to about "
            f"{max_hours} hours"
        )
    else:
        trail_query_main = (
            f"recommended {activity} trails in Yosemite National Park for {profile} "
            f"hikers, with trail descriptions"
        )

    # Secondary trail query explicitly referencing ThingsToDo-style info
    trail_query_things = (
        "Yosemite National Park official 'Things to Do' hiking and trail descriptions, "
        "including distance, difficulty, and who each hike is suitable for"
    )

    queries.append(trail_query_main)
    queries.append(trail_query_things)

    # --- Risk-aware / safety queries (LOWER weight) --------------------------
    if "weather_risk" in scores.risk_flags:
        queries.append(
            "weather safety and gear recommendations for hiking in Yosemite National Park"
        )

    if "access_risk" in scores.risk_flags:
        queries.append(
            "Yosemite National Park trail and road closures and how to adapt hiking plans"
        )

    # --- General planning query (LOWEST weight) ------------------------------
    queries.append(
        "trip planning tips for Yosemite National Park hiking, including how to choose "
        "appropriate trails based on skill level and conditions"
    )

    # 3) Ensure the vector index for this park exists and is populated
    embedder = LocalEmbedder()
    build_vector_index_for_park(trip.park_code, embedder)
    retriever = RAGRetriever(trip.park_code, embedder)

    # 4) RAG retrieval with bias:
    #    - Trail-focused queries get more top_k (more chunks)
    #    - Safety/planning queries get fewer results
    rag_chunks: List[DocumentChunk] = []

    for q in queries:
        # Heuristic: if the query is trail/hike-focused, pull more chunks
        q_lower = q.lower()
        is_trail_query = any(word in q_lower for word in ["trail", "hike", "hiking"])

        top_k = 4 if is_trail_query else 2

        results = retriever.search(q, top_k=top_k)
        for chunk, score in results:
            # Optional debug:
            # print(f"[DEBUG RAG] query={q!r} -> source={chunk.source}, doc_id={chunk.doc_id}")
            rag_chunks.append(chunk)

    # 5) De-duplicate chunks by (doc_id, chunk_id)
    seen = set()
    unique_chunks: List[DocumentChunk] = []
    for c in rag_chunks:
        key = (c.doc_id, c.chunk_id)
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    return {
        "trip": trip,
        "weather": weather_days,
        "scores": scores,
        "alerts": alerts,
        "rag_chunks": unique_chunks,
    }
