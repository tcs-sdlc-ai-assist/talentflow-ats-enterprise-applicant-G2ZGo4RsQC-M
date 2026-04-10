# TalentFlow ATS — Deployment Guide

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Variable Configuration](#environment-variable-configuration)
4. [Database Setup](#database-setup)
5. [Build Steps](#build-steps)
6. [Vercel Configuration (`vercel.json`)](#vercel-configuration)
7. [Deploying to Vercel](#deploying-to-vercel)
8. [Production Security Considerations](#production-security-considerations)
9. [CI/CD Notes](#cicd-notes)
10. [Troubleshooting](#troubleshooting)

---

## Overview

TalentFlow ATS is a Python FastAPI application designed for serverless deployment on Vercel. The application uses SQLite (via aiosqlite) for data persistence and Jinja2 for server-side rendered templates styled with Tailwind CSS.

---

## Prerequisites

- **Python 3.11+** installed locally
- **Node.js 18+** (required by Vercel CLI)
- **Vercel CLI** installed globally: `npm install -g vercel`
- A **Vercel account** linked to your Git provider (GitHub, GitLab, or Bitbucket)
- **Git** for version control

---

## Environment Variable Configuration

All configuration is managed through environment variables. In local development, create a `.env` file in the project root. For Vercel deployments, set these in the Vercel dashboard under **Project Settings → Environment Variables**.

### Required Variables

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Cryptographic key for JWT signing and session security. **Must be unique per environment.** | `a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9` |
| `DATABASE_URL` | SQLite connection string for aiosqlite. | `sqlite+aiosqlite:///./talentflow.db` |

### Optional Variables

| Variable | Description | Default |
|---|---|---|
| `ENVIRONMENT` | Deployment environment identifier. | `production` |
| `DEBUG` | Enable debug mode. **Must be `false` in production.** | `false` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token lifetime in minutes. | `30` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins. | `https://your-domain.vercel.app` |
| `LOG_LEVEL` | Python logging level. | `INFO` |

### Generating a Secure `SECRET_KEY`

```bash
# Option 1: Python
python -c "import secrets; print(secrets.token_hex(32))"

# Option 2: OpenSSL
openssl rand -hex 32
```

> **⚠️ CRITICAL:** Never commit your `.env` file or `SECRET_KEY` to version control. Add `.env` to `.gitignore`.

### Example `.env` File

```env
SECRET_KEY=your-generated-secret-key-here
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db
ENVIRONMENT=development
DEBUG=true
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
LOG_LEVEL=DEBUG
```

---

## Database Setup

### Local Development

TalentFlow ATS uses SQLite with async support via `aiosqlite`. The database file is created automatically on first startup.

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (tables are created automatically via lifespan handler)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The SQLite database file (`talentflow.db`) will be created in the project root directory.

### Vercel / Serverless

SQLite on Vercel has important limitations:

- **Vercel serverless functions have an ephemeral filesystem.** The SQLite database file is recreated on each cold start and is not shared across function instances.
- For **demo or low-traffic deployments**, this is acceptable — the lifespan handler will recreate tables on each cold start.
- For **production workloads requiring persistent data**, consider one of these alternatives:

| Option | Description |
|---|---|
| **Turso (libSQL)** | SQLite-compatible edge database. Drop-in replacement with `libsql-client`. |
| **PostgreSQL (Neon / Supabase)** | Replace `aiosqlite` with `asyncpg` and update `DATABASE_URL`. |
| **PlanetScale (MySQL)** | Replace with `aiomysql` driver and update models accordingly. |

To switch to an external database, update `DATABASE_URL` in your environment variables and install the appropriate async driver in `requirements.txt`.

### Database Migrations

For schema changes in production, use Alembic:

```bash
# Initialize Alembic (one-time setup)
alembic init alembic

# Generate a migration
alembic revision --autogenerate -m "describe your change"

# Apply migrations
alembic upgrade head
```

---

## Build Steps

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/your-org/talentflow-ats.git
cd talentflow-ats

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file with required variables
cp .env.example .env
# Edit .env with your values

# 5. Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Build

```bash
# Install production dependencies only
pip install -r requirements.txt --no-dev

# Verify the application starts without errors
python -c "from app.main import app; print('Build verification passed')"
```

---

## Vercel Configuration

### `vercel.json` Explanation

```json
{
  "version": 2,
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/app/static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ]
}
```

#### Breakdown

| Key | Purpose |
|---|---|
| `version` | Vercel platform version. Always `2`. |
| `builds[0].src` | Entry point for the Python serverless function. Points to the FastAPI app. |
| `builds[0].use` | Vercel builder. `@vercel/python` handles Python runtime, dependency installation, and ASGI wrapping. |
| `routes[0]` | Static file routing. Serves CSS, JS, and image assets directly without invoking the Python function. |
| `routes[1]` | Catch-all route. Forwards all non-static requests to the FastAPI application. |

### Important Notes on `vercel.json`

- The `@vercel/python` builder automatically detects `requirements.txt` and installs dependencies.
- The builder expects the ASGI app to be importable as `app` from the entry point module. Ensure `app/main.py` exposes `app = FastAPI(...)` at module level.
- Static files must be placed in a directory that matches the route pattern (e.g., `app/static/`).
- Vercel's Python runtime supports Python 3.12 by default. To pin a version, add a `runtime` field:

```json
{
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python",
      "config": {
        "runtime": "python3.11"
      }
    }
  ]
}
```

---

## Deploying to Vercel

### First-Time Setup

```bash
# 1. Login to Vercel
vercel login

# 2. Link the project
vercel link

# 3. Set environment variables
vercel env add SECRET_KEY
vercel env add DATABASE_URL

# 4. Deploy to preview
vercel

# 5. Deploy to production
vercel --prod
```

### Git-Based Deployments

Once linked to a Git repository in the Vercel dashboard:

- **Push to `main`** → automatic production deployment
- **Push to any other branch** → automatic preview deployment
- **Pull requests** → preview deployment with a unique URL

### Vercel Dashboard Configuration

1. Navigate to your project in the [Vercel Dashboard](https://vercel.com/dashboard)
2. Go to **Settings → General**:
   - Set **Framework Preset** to `Other`
   - Set **Root Directory** to `./` (or your monorepo path)
3. Go to **Settings → Environment Variables**:
   - Add all required variables for `Production`, `Preview`, and `Development` scopes
   - Use different `SECRET_KEY` values for each environment
4. Go to **Settings → Functions**:
   - Set **Region** to the region closest to your users
   - Set **Max Duration** as needed (default 10s, max 60s on Pro)

---

## Production Security Considerations

### SECRET_KEY Management

- **Generate a unique `SECRET_KEY` for every environment** (development, staging, production). Never reuse keys across environments.
- **Rotate the `SECRET_KEY` periodically.** Rotating the key invalidates all existing JWT tokens, forcing users to re-authenticate.
- **Never log or expose the `SECRET_KEY`** in error messages, API responses, or client-side code.
- Use Vercel's encrypted environment variables — they are encrypted at rest and injected at runtime.

### Secure Cookies

When deploying to production over HTTPS:

- Set `Secure=True` on all cookies so they are only transmitted over HTTPS.
- Set `HttpOnly=True` to prevent JavaScript access to authentication cookies.
- Set `SameSite=Lax` (or `Strict`) to mitigate CSRF attacks.
- Ensure your application configuration detects the `ENVIRONMENT` variable and applies secure cookie settings accordingly:

```python
# Example cookie configuration logic
SECURE_COOKIES = os.getenv("ENVIRONMENT", "production") == "production"

response.set_cookie(
    key="access_token",
    value=f"Bearer {token}",
    httponly=True,
    secure=SECURE_COOKIES,      # True in production (HTTPS only)
    samesite="lax",
    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
)
```

### CORS Configuration

- **Never use `allow_origins=["*"]` in production.** Explicitly list allowed origins.
- Set `CORS_ORIGINS` to your production domain(s):

```env
CORS_ORIGINS=https://talentflow.your-domain.com,https://www.your-domain.com
```

### Additional Security Hardening

| Measure | Implementation |
|---|---|
| **HTTPS enforcement** | Vercel handles TLS termination automatically. All `.vercel.app` domains are HTTPS by default. |
| **Rate limiting** | Add `slowapi` or Vercel's Edge Middleware for rate limiting on authentication endpoints. |
| **Input validation** | All request data is validated through Pydantic schemas. Never bypass schema validation. |
| **SQL injection prevention** | SQLAlchemy parameterized queries are used exclusively. Never construct raw SQL strings. |
| **Dependency auditing** | Run `pip audit` or `safety check` regularly to detect vulnerable packages. |
| **Password hashing** | All passwords are hashed with bcrypt. Plain-text passwords are never stored or logged. |
| **JWT token expiry** | Keep `ACCESS_TOKEN_EXPIRE_MINUTES` short (15–30 minutes) in production. |
| **Debug mode** | Ensure `DEBUG=false` in production. Debug mode exposes stack traces and internal state. |
| **Error responses** | Production error handlers return generic messages. Detailed errors are logged server-side only. |

---

## CI/CD Notes

### Recommended CI Pipeline (GitHub Actions)

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run linting
        run: |
          pip install ruff
          ruff check app/ tests/

      - name: Run type checking
        run: |
          pip install mypy
          mypy app/ --ignore-missing-imports

      - name: Run tests
        env:
          SECRET_KEY: test-secret-key-for-ci-only
          DATABASE_URL: sqlite+aiosqlite:///./test.db
          ENVIRONMENT: testing
          DEBUG: false
        run: |
          pytest tests/ -v --tb=short --asyncio-mode=auto

      - name: Check test coverage
        run: |
          pip install pytest-cov
          pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80
```

### CI/CD Best Practices

1. **Run tests before every deployment.** Vercel preview deployments do not run tests — your CI pipeline must gate merges.
2. **Use separate environment variables for CI.** Never use production secrets in CI. Use dedicated test values.
3. **Pin dependency versions** in `requirements.txt` for reproducible builds. Use `pip freeze > requirements.txt` after verifying a working environment.
4. **Run security scans** as part of CI:
   ```yaml
   - name: Security audit
     run: |
       pip install pip-audit
       pip-audit -r requirements.txt
   ```
5. **Branch protection rules:** Require passing CI checks before merging to `main`.
6. **Preview deployments:** Use Vercel's automatic preview deployments on pull requests for manual QA before merging.

### Deployment Flow

```
Developer pushes code
        │
        ▼
GitHub Actions CI runs
  ├── Linting (ruff)
  ├── Type checking (mypy)
  ├── Unit tests (pytest)
  └── Security audit (pip-audit)
        │
        ▼ (all checks pass)
PR merged to main
        │
        ▼
Vercel auto-deploys to production
        │
        ▼
Production health check
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError` on Vercel | Missing dependency in `requirements.txt` | Ensure all packages are listed. Run `pip freeze` to verify. |
| `500 Internal Server Error` | Unhandled exception in serverless function | Check Vercel function logs: `vercel logs --follow` |
| Database resets on each request | Ephemeral filesystem on Vercel | Expected with SQLite on serverless. Use an external database for persistence. |
| `422 Unprocessable Entity` | Request body doesn't match Pydantic schema | Check request payload against the schema definition. |
| Static files return 404 | Route mismatch in `vercel.json` | Verify the static route pattern matches your directory structure. |
| Slow cold starts | Large dependency bundle | Minimize dependencies. Remove unused packages from `requirements.txt`. |
| `SECRET_KEY` validation error | Environment variable not set | Add `SECRET_KEY` in Vercel dashboard for all environment scopes. |
| Cookie not persisting | `Secure=True` on HTTP | Use HTTPS in production. Set `Secure=False` for local HTTP development. |

### Viewing Logs

```bash
# Stream production logs
vercel logs --follow

# View recent logs
vercel logs

# View logs for a specific deployment
vercel logs <deployment-url>
```

### Local Debugging

```bash
# Run with verbose logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload

# Run tests with full output
pytest tests/ -v -s --tb=long
```