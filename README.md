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
