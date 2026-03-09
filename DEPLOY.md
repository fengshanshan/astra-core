# Deploy to Render.com

## Quick Deploy (Blueprint)

1. Push this repo to GitHub/GitLab/Bitbucket.
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect your repo and select it.
4. Render will create:
   - **PostgreSQL** database (`astra-db`)
   - **Web Service** (`astra-core`) linked to the database
5. In the Web Service → **Environment**, set **DEEPSEEK_API_KEY** (mark as "secret").
6. Deploy. Tables are created automatically on first startup via `init_db()`.

## Database Initialization

The app initializes the database on startup:

- **Tables**: `users`, `conversations`, `messages`, `system_prompt` are created by SQLAlchemy `create_all()`.
- **System prompt**: If `system_prompt` is empty, it seeds from `prompt.md`.

No manual migration is needed. The first request that triggers `init_db()` (or the startup event) will create everything.

## Environment Variables

| Variable | Required | Set by | Description |
|----------|----------|--------|-------------|
| `DATABASE_URL` | Yes | Render (auto from PostgreSQL) | Connection string. Render uses `postgres://`; the app converts to `postgresql://` for psycopg2. |
| `DEEPSEEK_API_KEY` | Yes | You | DeepSeek API key for LLM. Add in Render Dashboard → Environment. |

## Manual Setup (without Blueprint)

If you prefer to create services manually:

### 1. Create PostgreSQL Database

- **New** → **PostgreSQL**
- Plan: Free (or paid)
- Note the **Internal Database URL** (use this for the web service)

### 2. Create Web Service

- **New** → **Web Service**
- Connect repo, select branch
- **Build Command**: `bash build.sh`
- **Start Command**: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT`
- **Environment**:
  - `DATABASE_URL` → from the PostgreSQL service (Internal URL)
  - `DEEPSEEK_API_KEY` → your key (add as secret)

### 3. Ephemeris Data

Chart calculation uses Swiss Ephemeris data from the `ephemeris/` folder. Ensure the full ephemeris files are committed to the repo.

## Health Check

The service exposes `/api/health`. Render uses it for health checks. Response: `{"status": "chart service running"}`.

## Troubleshooting

- **Database connection failed**: Ensure `DATABASE_URL` is set and the web service is in the same Render region as the database (use Internal URL).
- **Chart calculation fails**: Ensure `ephemeris/` folder contains the Swiss Ephemeris data files.
- **502 Bad Gateway**: App may be crashing. Check logs; common causes: missing `DEEPSEEK_API_KEY`, database not ready.
