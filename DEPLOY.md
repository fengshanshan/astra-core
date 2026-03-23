# Deploy to Render.com

## Quick Deploy (Blueprint)

1. Push this repo to GitHub/GitLab/Bitbucket.
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect your repo and select it.
4. Render will create:
   - **PostgreSQL** database (`astra-db`)
   - **Web Service** (`astra-core`) linked to the database
5. In the Web Service → **Environment**, set **DEEPSEEK_API_KEY** (mark as "secret").
6. 在 Environment 中设置 `INIT_DB=true`，触发一次 Manual Deploy 初始化数据库，完成后将 `INIT_DB` 改回 `false`。

## Database Initialization

数据库初始化**不会**在服务启动时自动执行，需要手动触发。

### 本地初始化

```bash
python scripts/init_db.py
```

### Render.com 初始化

数据库初始化在 **build 阶段**通过环境变量 `INIT_DB` 控制：

1. Render Dashboard → Web Service → **Environment**
2. 添加环境变量 `INIT_DB` = `true`
3. 手动触发一次 **Manual Deploy**（Render 会在 build 时执行 `scripts/init_db.py`）
4. 部署成功后，将 `INIT_DB` 改回 `false`（或删除该变量），避免下次 deploy 重复初始化

> ⚠️ 每次设置 `INIT_DB=true` deploy 都会重新建表（`create_all` 幂等，不会删数据），但如果你手动清空了数据库再 init，旧数据会丢失。

## Environment Variables

| Variable | Required | Set by | Description |
|----------|----------|--------|-------------|
| `DATABASE_URL` | Yes | Render (auto from PostgreSQL) | Connection string. Render uses `postgres://`; the app converts to `postgresql://` for psycopg2. |
| `DEEPSEEK_API_KEY` | Yes | You | DeepSeek API key for LLM. Add in Render Dashboard → Environment. |
| `INIT_DB` | No | You | 设为 `true` 时，build 阶段自动初始化数据库建表。完成后改回 `false`。 |

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
