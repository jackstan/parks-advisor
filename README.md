# 🏞️ Parks Advisor

Parks Advisor is a real-data, RAG-augmented trip-planning and safety advisor for U.S. National Parks.

It combines:

- **Live weather** (Open-Meteo)
- **Official NPS alerts** (closures, conditions)
- **Official NPS content** (articles + Things To Do)
- A simple **LLM advisor** that scores your trip and explains risks in plain language

You can run it via:

- A **CLI demo** (`app.py`)
- A **Streamlit UI** (`ui_streamlit.py`)

---

## ✨ Features

- **Trip scoring**
  - Access score (closures, alerts)
  - Weather score (temp, precip, wind)
  - Crowd/seasonality signal
  - Overall trip readiness

- **RAG over NPS content**
  - Ingests:
    - NPS *articles* for conditions / safety / background
    - NPS *Things To Do* for activity and hike descriptions
  - Stores chunks in a local **Chroma** vector DB
  - Uses a local embedding model (SentenceTransformers)

- **LLM-backed advisor**
  - Builds a structured, “LLM-ready” prompt:
    - Trip details
    - Scores + notes + risk flags
    - Weather forecast (°F, mph)
    - NPS alerts
    - Relevant RAG snippets with sources
  - Calls an OpenAI model to produce:
    - A verdict: `GO`, `GO-WITH-CAUTION`, or `AVOID`
    - A multi-paragraph explanation
    - Risk discussion + gear recommendations

- **Streamlit UI**
  - Choose park, dates, activity, and hiker profile
  - See scores, weather table, alerts list, and the advisor’s narrative

---

## 🧱 Project Structure

```text
parks-advisor/
│
├── app.py                  # CLI entrypoint – runs a single demo trip
├── ui_streamlit.py         # Streamlit UI for interactive use
│
├── README.md
├── requirements.txt
├── .gitignore
│
└── src/
    ├── config.py           # Env loading, park metadata (including NPS /parks bootstrap)
    ├── models.py           # Core dataclasses:
    │   - TripRequest
    │   - WeatherDay
    │   - Alert
    │   - Scores
    │   - DocumentChunk
    │   - ThingsToDoItem
    │
    ├── weather_client.py   # Open-Meteo client (daily forecast, °C + m/s → °F + mph)
    ├── nps_client.py       # NPS alerts client
    ├── nps_articles.py     # NPS articles client
    ├── nps_things_to_do.py # NPS "Things To Do" client
    │
    ├── scoring.py          # Trip scoring:
    │   - access_score
    │   - weather_score
    │   - crowd / season heuristics
    │   - trip_readiness_score
    │
    ├── embeddings/
    │   ├── base.py         # Abstract Embedder
    │   └── local_embedder.py   # SentenceTransformers-based embedder
    │
    ├── rag/
    │   ├── chunking.py     # Chunking logic for article/ThingsToDo text
    │   ├── index_builder.py# Builds/updates Chroma index per park
    │   └── retriever.py    # RAGRetriever: semantic search over stored chunks
    │
    ├── advisor_context.py  # Orchestrates:
    │                       # - weather
    │                       # - alerts
    │                       # - scores
    │                       # - RAG retrieval
    │                       # Returns a unified context dict
    │
    ├── prompt_builder.py   # Builds the full LLM prompt from context
    └── advisor_llm.py      # High-level advisor:
                            # - build context
                            # - build prompt
                            # - call OpenAI LLM
                            # - return (scores, explanation, prompt_debug)

