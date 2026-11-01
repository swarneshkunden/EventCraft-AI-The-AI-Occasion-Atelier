# Architecture

EventCraft AI is a small, single-service web app: a FastAPI + SQLAlchemy backend
that also serves a dependency-free vanilla-JS SPA. There is no build step for the
frontend and no separate API host, so `run.bat` is enough to run everything.

## Layout

```
backend/
  app/
    main.py              # app factory, middleware, routers, SPA mount
    errors.py            # domain errors (AppError and friends)
    config/              # settings, database engine/session, logging
    models/models.py     # SQLAlchemy ORM models
    validators/schemas.py# Pydantic request/response contracts
    middleware/          # security headers, rate limiting, error handlers
    routes/              # HTTP layer: parse, call a service, return a schema
    services/            # business logic, AI pipeline, seeding
  migrations/            # Alembic
  tests/                 # pytest (integration + unit)

frontend/
  index.html
  src/
    app.js               # hash router and page mounting
    pages/               # one module per screen
    components/          # shared UI (navbar, sidebar, modal, ui builders)
    services/            # fetch wrappers and auth state
    utils/               # formatters, HTML escaping, icons, toasts, theme
  tests/                 # node --test suites
```

## Request lifecycle

1. **Middleware** wraps every request: `SecurityHeadersMiddleware` adds headers,
   `RateLimitMiddleware` enforces per-IP/per-user limits, CORS allows the SPA
   origin, and a request ID is attached to `request.state`.
2. **Route** (`app/routes/*.py`) declares a Pydantic `response_model`, resolves
   the current user, and calls a service. Routes contain no business rules.
3. **Service** (`app/services/*.py`) owns queries and invariants. Multi-tenant
   access is enforced here: `_assert_owner` checks the event owner, and
   `_get_owned` scopes every child lookup to both its ID and its event ID, so a
   child ID from another event resolves to 404 rather than leaking data.
4. **Models** map to SQLite locally and PostgreSQL (psycopg) in deployment.
   Every write goes through the ORM, never string-built SQL.
5. **Response** is serialized by the declared `response_model`. A route without
   one is treated as a contract bug and is pinned by
   `tests/test_openapi_contracts.py`.

### Errors

Services raise domain errors from `app/errors.py`; they never import
`HTTPException`. The handlers in `app/middleware/error_handlers.py` translate
them:

| Error | Status | Client detail |
| --- | --- | --- |
| `NotFoundError` | 404 | the curated message |
| `ForbiddenError` | 403 | the curated message |
| `ConflictError` | 409 | the curated message |
| `InvalidRequestError` | 400 | the curated message |
| `AIUnavailableError` | 503 | friendly "try again" message |
| `AIResponseError` | 502 | generic "request could not be completed" |
| validation / SQLAlchemy / unexpected | 400 / 500 / 500 | generic |

Internal detail (tracebacks, SQL, provider payloads) is logged server-side only.
`auth_service.py` deliberately keeps `HTTPException(401)` because the global
handler sanitizes every 401 to `"Authentication required"`.

## AI pipeline

All structured generation goes through `app/services/ai_generation.py`:

```
call_ai() -> is_ai_fallback? -> extract_json_from_response() -> schema.model_validate()
```

- `generate_model()` is the single entry point; it raises `AIUnavailableError`
  when the provider reports an outage and `AIResponseError` when the payload is
  not valid JSON or fails the schema. When `GEMINI_API_KEY` is blank,
  `_call_gemini()` returns the fallback immediately instead of attempting a
  doomed network call, so local and CI runs stay fast and offline.
- `generate_with_fallback()` degrades **only** on `AIUnavailableError`, returning
  deterministic defaults from `app/services/ai_fallbacks.py` and `used_ai=False`.
  Malformed output still returns 502 on purpose: a broken contract should be
  visible, an outage should not break the demo.
- `mark_source()` sets `X-AI-Source: ai | fallback` on the response, and
  `AI_SOURCE_RESPONSES` documents the header in OpenAPI.
- Prompts live in `app/services/prompts.py`; the cache key includes
  `PROMPT_VERSION`, so editing a prompt invalidates cached answers.

Features using the pipeline: budget split, task/timeline generation, vendor
checklist + questions, and personalised ideas. The chat reply and the crisis
intent classifier are free-form and use `call_ai()` directly through their own
validated paths.

## Auth and security

- Passwords use bcrypt; the login path always verifies against a dummy hash when
  the user does not exist, to avoid timing leaks.
- Access tokens are short-lived HS256 JWTs. Refresh tokens are opaque random
  strings stored only as SHA-256 hashes; rotation revokes the old token, and
  replays are rejected.
- Both tokens are `httpOnly` cookies; the SPA never reads them from JS.
- Auth failures use exponential backoff per account and per IP, and the rate
  limiter covers the rest of the API.
- All input is validated by Pydantic with explicit length/range limits; CSV
  import caps file size and row count and neutralises formula injection on
  export.
- CSRF defence is `SameSite=Lax` cookies plus CORS restricted to configured
  origins.

## Frontend

- Hash-based router in `src/app.js`; each page exports a `render*Page()` that
  returns an HTML string and an optional mount function for listeners.
- All dynamic text is escaped. `utils/html.js` provides an escape-by-default
  `html` tagged template and an explicit `raw()` opt-out; `components/ui.js`
  holds the repeated page chrome (`emptyState`, `statCard`, `filterTabs`,
  `bindFilterButtons`).
- State lives in module-level variables per page plus `services/` wrappers for
  `fetch`, so no framework or build tool is required.

## Testing and quality gates

- `backend/tests` – pytest integration tests against in-memory SQLite (or
  `TEST_DATABASE_URL` for PostgreSQL), with a `test_idor.py` matrix proving one
  user cannot reach another user's resources.
- `frontend/tests` – `node --test` for formatters and HTML helpers.
- Coverage gate: 92% minimum (`pytest --cov=app --cov-fail-under=92`).
- `ruff check` + `ruff format --check` for Python; ESLint 9 + `npm test` for JS.
- CI runs all of the above, plus `pip-audit`; `.pre-commit-config.yaml` mirrors
  the Python checks locally.

## Deferred work

**`Task.depends_on` uses titles, not IDs.** A task stores the *titles* of the
tasks it depends on, so renaming a task silently breaks the dependency graph and
readiness calculation. Migrating to IDs needs a schema change plus a data
backfill (map each stored title to the sibling task's ID per event), a readiness
query change, and prompt-contract changes for AI-generated tasks. It is
intentionally out of scope for the current cleanup and should ship with its own
migration and tests.
