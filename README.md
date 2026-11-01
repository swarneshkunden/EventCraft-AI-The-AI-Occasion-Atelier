# EventCraft AI

EventCraft AI is a web app for planning weddings, birthdays, and community events. It brings budgets, tasks, vendors, guests, and AI-assisted ideas into one place. Budget and AI suggestions are estimates; verify details before making decisions.

## Setup

Requirements: Python 3.11 and pip.

From the project root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

In `.env`, replace `APP_SECRET_KEY` with a random value of at least 32 characters. `DATABASE_URL` defaults to local SQLite; `GEMINI_API_KEY` is optional and enables live AI responses.

Apply database migrations and start the app:

```powershell
Set-Location backend
python -m alembic upgrade head
Set-Location ..
.\run.bat
```

Open <http://127.0.0.1:8000>.

## Environment variables

- `APP_SECRET_KEY` (required): random signing key, at least 32 characters.
- `APP_ENV`: `development`, `test`, or `production` (default: `development`).
- `DATABASE_URL`: SQLAlchemy URL (default: `sqlite:///./eventplanner.db`); use PostgreSQL for persistent deployment storage.
- `DATABASE_URL_DIRECT` (optional): direct PostgreSQL connection for migrations.
- `ALLOWED_ORIGINS`: comma-separated browser origins.
- `GEMINI_API_KEY` (optional): server-side Gemini API key.
- `GEMINI_MODEL`: Gemini model identifier (default: `gemini-3.8-flash`).
- `CURRENCY`: display currency (default: `INR`).

Additional database, AI, request-limit, and upload settings are defined in `backend/app/config/settings.py`.

## Testing and code quality

Backend (from the project root):

```powershell
Set-Location backend
python -m pip install pytest-cov ruff
..\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
Set-Location ..
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend scripts
.\.venv\Scripts\python.exe -m ruff format --check --config backend/pyproject.toml backend scripts
```

Frontend (Node 20+):

```powershell
Set-Location frontend
npm ci
npm run lint
npm test
Set-Location ..
```

Install the optional Git hooks with `pip install pre-commit` and `pre-commit install`.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module responsibilities, the AI
pipeline, the error model, and the authorization rules.

## Deployment

1. Copy `.env.example` to `.env` and replace `APP_SECRET_KEY` with a fresh random value (32+ characters):
   ```powershell
   Copy-Item .env.example .env
   ```
2. Set `DATABASE_URL` to a durable PostgreSQL connection (SQLite is ephemeral and unsuitable for production).
3. For production, set `APP_ENV=production` and `ALLOWED_ORIGINS` to your HTTPS origins only. The settings validator rejects ephemeral SQLite, example secrets, and non-HTTPS origins in production.
4. Run migrations and start the server:
   ```powershell
   Set-Location backend
   python -m alembic upgrade head
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
   ```
   Or build and run with Docker:
   ```powershell
   docker-compose up -d postgres
   docker build -t eventcraft-ai .
   docker run -p 8080:8080 --env-file .env eventcraft-ai
   ```
5. The `/healthz` endpoint probes database connectivity and is suitable for a load-balancer health check. `/api/health` returns process health.
