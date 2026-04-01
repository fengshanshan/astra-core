# Chart Service

Western astrology natal chart calculation and AI interpretation service based on birth information.

## Overview

Natal chart calculation + RAG knowledge base + DeepSeek LLM, providing chart data and astrological Q&A. Users input birth date, time, and place to get chart interpretation and ask questions based on their chart.

```
User input (birth info + question)
    → Chart calculation (Swiss Ephemeris)
    → RAG knowledge matching
    → DeepSeek generates interpretation
    → Return answer
```

---

## Project Structure

```
astra-core/
├── app/
│   ├── main.py              # FastAPI entry, API routes, static file serving
│   ├── services/
│   │   ├── chart_service.py # Chart calculation (planets, houses, aspects)
│   │   ├── chat_service.py  # RAG: feature matching against knowledge base
│   │   └── llm_service.py   # DeepSeek API client
│   └── knowledge/
│       └── knowledge_base.py # Knowledge base (signs, retrogrades, aspects)
├── schemas.py           # Request/response models
├── prompt.md            # Astrologer system prompt
├── ephemeris/           # Swiss Ephemeris data (download separately)
├── frontend/            # Frontend UI
│   ├── index.html      # Main page (user identity → chat)
│   ├── chat.js
│   ├── chat.css
│   ├── prompt.html     # System prompt editor
│   └── style.css
├── pyproject.toml
└── .env                 # DEEPSEEK_API_KEY
```

---

## Core Modules

| Module | Responsibility |
|--------|----------------|
| **chart_service** | Local time → UTC, planet positions, Placidus houses, aspect calculation, feature generation |
| **chat_service** | Match features against knowledge base for interpretation text |
| **llm_service** | Call DeepSeek, combine prompt.md with RAG results to generate answers |
| **knowledge_base** | Predefined interpretations for signs, retrogrades, aspects |

---

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page (chat flow) |
| `/api/health` | GET | Health check |
| `/api/calculate-chart` | POST | Calculate chart |
| `/api/chat` | POST | Chart + question → AI interpretation |

### Request Example

**calculate-chart / chat**

```json
{
  "date": "1994-11-03",
  "time": "21:30",
  "latitude": 37.98,
  "longitude": 23.72
}
```

**chat additional field**

```json
{ "question": "What are the characteristics of my sun sign?" }
```

Latitude and longitude are optional; omit to use China timezone (Beijing).

---

## Frontend

- User identity (wechat_id) → new user: birth form with map; existing user: direct to chat
- Birthplace selection: optional city search (Amap geocoding when `AMAP_KEY` is set)
- Chart summary display
- Multi-turn astrological chat

---

## Run

```bash
# Install dependencies
uv sync

# Start (use python -m so uvicorn reload subprocess uses project venv)
uv run python -m uvicorn app.main:app --reload
```

Visit <http://localhost:8000>

**Prerequisites:**

- PostgreSQL running with database `astra` (or set `DATABASE_URL` in `.env`)
- Swiss Ephemeris data in `ephemeris/` folder: `sepl_18.se1`, `semo_18.se1` (planets); `seas_18.se1` for Chiron/Juno

---

## Deploy to Render

See [DEPLOY.md](DEPLOY.md) for full instructions. Quick: push to GitHub → Render Dashboard → New → Blueprint → connect repo → set `DEEPSEEK_API_KEY` → deploy.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `DATABASE_URL` | PostgreSQL connection string (e.g. `postgresql://user:pass@localhost/astra`) |

---

## Dependencies

- **pyswisseph**: Chart calculation
- **timezonefinder**: Coordinates → timezone
- **openai**: DeepSeek client (OpenAI-compatible API)
- **fastapi**: Web framework
