# TalentFlow ATS

**Applicant Tracking System** — A modern, full-featured recruitment management platform built with Python and FastAPI.

## Overview

TalentFlow ATS streamlines the hiring process by providing a centralized platform for managing job postings, candidate applications, interview scheduling, feedback collection, and hiring decisions. Designed for HR teams, hiring managers, and recruiters to collaborate efficiently throughout the recruitment lifecycle.

## Features

- **Job Management** — Create, publish, and manage job postings with detailed descriptions, requirements, and metadata
- **Candidate Tracking** — Track candidates through configurable hiring pipelines from application to offer
- **Application Processing** — Receive, review, and advance applications through customizable workflow stages
- **Interview Scheduling** — Schedule interviews, assign interviewers, and manage interview panels
- **Feedback & Evaluation** — Collect structured interview feedback and scorecards from interviewers
- **User Roles & Permissions** — Role-based access control for Super Admins, Hiring Managers, Recruiters, Interviewers, and Viewers
- **Audit Logging** — Full audit trail of all actions for compliance and accountability
- **Search & Filtering** — Advanced search across candidates, jobs, and applications
- **Dashboard & Analytics** — Overview dashboards with key recruitment metrics

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | FastAPI (Python 3.11+) |
| **Database** | SQLite (via aiosqlite for async) |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Authentication** | JWT (python-jose) + bcrypt password hashing |
| **Validation** | Pydantic v2 |
| **Configuration** | pydantic-settings + .env |
| **Templating** | Jinja2 |
| **Styling** | Tailwind CSS (via CDN) |
| **Testing** | pytest + pytest-asyncio + httpx |
| **Server** | Uvicorn (ASGI) |

## Folder Structure

```
talentflow-ats/
├── app/
│   ├── core/
│   │   ├── config.py          # Application settings (BaseSettings)
│   │   ├── database.py        # Async SQLAlchemy engine & session
│   │   ├── security.py        # JWT token creation/verification, password hashing
│   │   └── __init__.py
│   ├── models/
│   │   ├── user.py            # User model
│   │   ├── job.py             # Job model
│   │   ├── candidate.py       # Candidate model (+ candidate_skills association)
│   │   ├── application.py     # Application model
│   │   ├── interview.py       # Interview, InterviewAssignment, InterviewFeedback models
│   │   ├── audit_log.py       # AuditLog model
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── user.py            # User request/response schemas
│   │   ├── job.py             # Job request/response schemas
│   │   ├── candidate.py       # Candidate request/response schemas
│   │   ├── application.py     # Application request/response schemas
│   │   ├── interview.py       # Interview request/response schemas
│   │   ├── audit_log.py       # AuditLog response schemas
│   │   └── __init__.py
│   ├── services/
│   │   ├── user.py            # User business logic
│   │   ├── job.py             # Job business logic
│   │   ├── candidate.py       # Candidate business logic
│   │   ├── application.py     # Application business logic
│   │   ├── interview.py       # Interview business logic
│   │   ├── audit_log.py       # Audit logging service
│   │   └── __init__.py
│   ├── routers/
│   │   ├── auth.py            # Authentication routes (login, register, logout)
│   │   ├── users.py           # User management routes
│   │   ├── jobs.py            # Job CRUD routes
│   │   ├── candidates.py      # Candidate CRUD routes
│   │   ├── applications.py    # Application workflow routes
│   │   ├── interviews.py      # Interview scheduling routes
│   │   ├── dashboard.py       # Dashboard & analytics routes
│   │   └── __init__.py
│   ├── dependencies/
│   │   ├── auth.py            # get_current_user, role-based guards
│   │   └── __init__.py
│   ├── templates/
│   │   ├── base.html          # Base layout with navigation
│   │   ├── auth/              # Login, register templates
│   │   ├── dashboard/         # Dashboard templates
│   │   ├── jobs/              # Job listing, detail, form templates
│   │   ├── candidates/        # Candidate listing, detail templates
│   │   ├── applications/      # Application listing, detail templates
│   │   └── interviews/        # Interview listing, detail templates
│   └── main.py               # FastAPI app entry point
├── tests/
│   ├── test_auth.py           # Authentication tests
│   ├── test_jobs.py           # Job endpoint tests
│   ├── test_candidates.py     # Candidate endpoint tests
│   ├── test_applications.py   # Application endpoint tests
│   └── conftest.py            # Shared fixtures
├── .env                       # Environment variables (not committed)
├── .env.example               # Example environment variables
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd talentflow-ats
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update values:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Application
APP_NAME=TalentFlow ATS
DEBUG=true

# Security
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db

# CORS
CORS_ORIGINS=["http://localhost:8000"]
```

> **Important:** Generate a strong `SECRET_KEY` for production:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(64))"
> ```

### 5. Run Database Migrations

The database tables are created automatically on first startup via SQLAlchemy's `create_all()`. No manual migration step is required for initial setup.

For a fresh database reset:

```bash
rm talentflow.db    # Delete existing database
# Tables will be recreated on next server start
```

### 6. Start the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:

- **Web UI:** [http://localhost:8000](http://localhost:8000)
- **API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Docs (ReDoc):** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Usage Guide by Role

### Super Admin

- Full access to all features and settings
- Manage users: create accounts, assign roles, deactivate users
- View audit logs for compliance tracking
- Access all jobs, candidates, applications, and interviews across the organization

### Hiring Manager

- Create and manage job postings for their department
- Review applications and advance candidates through pipeline stages
- Schedule interviews and assign interview panels
- Make hiring decisions (approve/reject candidates)
- View dashboard with hiring metrics for their jobs

### Recruiter

- Source and add candidates to the system
- Submit applications on behalf of candidates
- Coordinate interview scheduling
- Manage candidate communications
- Track pipeline progress across active jobs

### Interviewer

- View assigned interview schedules
- Submit structured feedback and scorecards after interviews
- View candidate profiles for upcoming interviews

### Viewer

- Read-only access to job postings and candidate pipelines
- View interview schedules and feedback (no edit permissions)

## API Endpoint Summary

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login and receive JWT token |
| `POST` | `/api/auth/logout` | Logout (invalidate session) |
| `GET` | `/api/auth/me` | Get current user profile |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users` | List all users (admin only) |
| `GET` | `/api/users/{id}` | Get user by ID |
| `PUT` | `/api/users/{id}` | Update user |
| `DELETE` | `/api/users/{id}` | Deactivate user (admin only) |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/jobs` | List jobs (with filters) |
| `POST` | `/api/jobs` | Create a new job posting |
| `GET` | `/api/jobs/{id}` | Get job details |
| `PUT` | `/api/jobs/{id}` | Update job posting |
| `DELETE` | `/api/jobs/{id}` | Delete/archive job |

### Candidates

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/candidates` | List candidates (with search) |
| `POST` | `/api/candidates` | Add a new candidate |
| `GET` | `/api/candidates/{id}` | Get candidate profile |
| `PUT` | `/api/candidates/{id}` | Update candidate info |
| `DELETE` | `/api/candidates/{id}` | Remove candidate |

### Applications

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/applications` | List applications (with filters) |
| `POST` | `/api/applications` | Submit a new application |
| `GET` | `/api/applications/{id}` | Get application details |
| `PUT` | `/api/applications/{id}` | Update application |
| `PATCH` | `/api/applications/{id}/stage` | Advance/move application stage |
| `PATCH` | `/api/applications/{id}/status` | Update application status |

### Interviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/interviews` | List interviews |
| `POST` | `/api/interviews` | Schedule a new interview |
| `GET` | `/api/interviews/{id}` | Get interview details |
| `PUT` | `/api/interviews/{id}` | Update interview |
| `DELETE` | `/api/interviews/{id}` | Cancel interview |
| `POST` | `/api/interviews/{id}/feedback` | Submit interview feedback |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/stats` | Get recruitment statistics |
| `GET` | `/api/dashboard/pipeline` | Get pipeline overview |

### Audit Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/audit-logs` | List audit logs (admin only) |

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_auth.py

# Run with coverage report
pytest --cov=app --cov-report=term-missing
```

## Deployment Notes

### Production Checklist

1. **Environment Variables**
   - Set `DEBUG=false`
   - Generate a strong, unique `SECRET_KEY`
   - Configure `CORS_ORIGINS` with your production domain(s)
   - Use a production database URL (PostgreSQL recommended for production)

2. **Database**
   - SQLite is suitable for development and small deployments
   - For production at scale, migrate to PostgreSQL by updating `DATABASE_URL`:
     ```env
     DATABASE_URL=postgresql+asyncpg://user:password@host:5432/talentflow
     ```
   - Add `asyncpg` to `requirements.txt` when using PostgreSQL

3. **Running in Production**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
   Or use Gunicorn with Uvicorn workers:
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

4. **Reverse Proxy**
   - Place behind Nginx or Caddy for TLS termination, static file serving, and load balancing

5. **Docker** (optional)
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   EXPOSE 8000
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

6. **Security Hardening**
   - Enable HTTPS only
   - Set secure cookie flags
   - Rate limit authentication endpoints
   - Regularly rotate `SECRET_KEY`
   - Keep dependencies updated

## License

**Private** — All rights reserved. This software is proprietary and confidential. Unauthorized copying, distribution, or use of this software is strictly prohibited.