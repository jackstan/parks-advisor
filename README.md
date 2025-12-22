# 🏞️ Parks Advisor

<p align="center">
  <img src="https://images.unsplash.com/photo-1508264165352-258859e62245?q=80&w=1400&auto=format&fit=crop" width="90%" />
</p>

Parks Advisor is a real-data, RAG-augmented trip-planning and safety advisor for U.S. National Parks.

It combines:

- **Live weather** (Open-Meteo)
- **Official NPS alerts** (closures, conditions)
- **Official NPS content** (articles + Things To Do)
- **Trail geometry data** (NPS ArcGIS)
- A simple **LLM advisor** that scores your trip and explains risks in plain language

The project is currently **optimized for Yosemite National Park**.

You can run it via:

- A **CLI demo** (`app.py`)
- A **Streamlit UI** (`ui_streamlit.py`)

---

## ✨ Features

### Trip scoring

- Access score (closures, alerts)
- Weather score (temp, precip, wind)
- Crowd / seasonality signal
- Overall trip readiness

### Trail-aware recommendations

- Ingests official NPS trail geometry (ArcGIS)
- Classifies trails as loops, out-and-back, or networks
- Produces realistic distance ranges (round-trip estimates)
- Filters trails based on access, closures, and time constraints

### RAG over NPS content

- Ingests:
  - NPS *articles* for conditions / safety / background
  - NPS *Things To Do* for activity and hike descriptions
- Stores chunks in a local **Chroma** vector DB
- Uses a local embedding model (SentenceTransformers)

### LLM-backed advisor

- Builds a structured, “LLM-ready” prompt:
  - Trip details
  - Scores + notes + risk flags
  - Weather forecast (°F, mph)
  - NPS alerts
  - Relevant RAG snippets
  - Suggested trail options
- Calls an OpenAI model to produce:
  - A verdict: `GO`, `GO-WITH-CAUTION`, or `AVOID`
  - A multi-paragraph explanation
  - Risk discussion + gear recommendations

### Streamlit UI

- Choose dates, activity, and hiker profile
- View scores, weather table, alerts, and advisor output
- Park selection is currently locked to **Yosemite** to match tuned prompts and trail logic

---

## 🚀 How to run it

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
### 2. Set environment variables

Create a .env file in the project root:
```bash
OPENAI_API_KEY=your_openai_key_here
NPS_API_KEY=your_nps_api_key_here
```
(Open-Meteo does not require an API key.)

### 3. Run the CLI demo
```bash
python app.py
```
### 4. Run the Streamlit UI
```bash
streamlit run ui_streamlit.py
```
## 🧱 Project structure
```text
parks-advisor/
│
├── app.py                      # CLI demo entrypoint
├── ui_streamlit.py             # Streamlit UI
│
├── README.md
├── requirements.txt
├── .gitignore
│
└── src/
    ├── config.py               # Env loading and park metadata
    ├── models.py               # Core dataclasses:
    │   - TripRequest
    │   - WeatherDay
    │   - Alert
    │   - Scores
    │   - DocumentChunk
    │   - TrailCard
    │
    ├── weather_client.py       # Open-Meteo client
    ├── nps_client.py           # NPS alerts client
    ├── nps_articles.py         # NPS articles client
    ├── nps_things_to_do.py     # NPS Things To Do client
    ├── trails_arcgis.py        # NPS ArcGIS trails ingestion and geometry logic
    │
    ├── scoring.py              # Trip scoring logic
    │
    ├── embeddings/
    │   ├── base.py
    │   └── local_embedder.py
    │
    ├── rag/
    │   ├── chunking.py
    │   ├── index_builder.py
    │   └── retriever.py
    │
    ├── advisor_context.py      # Orchestrates weather, alerts, scores, trails, and RAG
    ├── prompt_builder.py       # Builds the full LLM prompt
    └── advisor_llm.py          # Calls the LLM and returns scores and explanation
```
