# Web-Weebforce - Contract Verifier

Contract Verifier is a full-stack app for:
- uploading contract files
- verifying SHA-256 integrity
- managing contract clauses
- importing legal reference data and risk rules from Excel

This repo is designed to run with:
- PostgreSQL running in Docker on the host machine
- backend and frontend running in Docker containers
- optional data import from the `data/` folder

## Project Layout

```text
backend/                  FastAPI backend
frontend/                 React/Vinext frontend
data/                     Excel references and sample contracts
docker-compose.yml        Backend + frontend stack
.env.example              Environment template
```

## What Runs Automatically

- The backend creates the database schema on startup.
- No users, contracts, or verification logs are seeded automatically.
- Sample/reference data is imported only when you run the import job manually.

## Prerequisites

- Docker Desktop
- PostgreSQL container running on the host machine and exposed on port `5432`
- DBeaver or another DB client if you want to inspect the database

## Database Setup

Use PostgreSQL credentials that match your running container:

```text
Host: localhost
Port: 5432
User: admin
Password: matkhau_xinfu
Database: contract_verifier_db
```

The backend container must connect to the host machine through:

```text
postgresql://admin:matkhau_xinfu@host.docker.internal:5432/contract_verifier_db
```

## Quick Start

1. Copy `.env.example` to `.env`
2. Keep or edit these values:

```env
DATABASE_URL=postgresql://admin:matkhau_xinfu@host.docker.internal:5432/contract_verifier_db
CORS_ORIGINS=*
BACKEND_INTERNAL_URL=http://backend:8000
```

3. Start the web app:

```bash
docker compose up --build
```

4. Open the app:
- Frontend: `http://localhost:3000`
- Backend health check: `http://localhost:8000/health`

If you are on another laptop in the same network, replace `localhost` with the host machine IP, for example:

- Frontend: `http://192.168.1.20:3000`
- Backend health check: `http://192.168.1.20:8000/health`

## Import Sample Data

The app starts empty by default. To load the Excel-based reference data and sample contracts from `data/`:

```bash
docker compose --profile seed run --rm import-data
```

The import job is idempotent for the dedicated import account. It removes previously imported rows for that account before inserting fresh data.

## Docker Services

The Compose stack includes:
- `backend`: FastAPI API
- `frontend`: web UI
- `import-data`: manual seed/import job

The backend and importer both use `DATABASE_URL` from the environment, so they can connect to the PostgreSQL container already running on your host.

## Frontend Behavior

The frontend proxies API requests to the backend container, so you can use the app from a single origin in Docker.

If you run frontend and backend separately, set:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

If you run through Docker Compose, you can leave `NEXT_PUBLIC_API_BASE_URL` empty.

## Local Dev Without Docker

If you want to run only the backend locally:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy psycopg2-binary pandas openpyxl bcrypt python-multipart
uvicorn backend.main:app --reload
```

If you want to run only the frontend locally:

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/users/register` | Register |
| POST | `/api/users/login` | Login |
| GET | `/api/auth/me` | Current user |
| POST | `/api/contracts` | Upload contract |
| GET | `/api/contracts/{id}` | Get contract metadata |
| POST | `/api/contracts/{id}/verify` | Verify SHA-256 |
| POST | `/api/contracts/{id}/clauses` | Add clause |
| PUT | `/api/contracts/{id}/clauses/{clause_id}` | Update clause |
| DELETE | `/api/contracts/{id}/clauses/{clause_id}` | Delete clause |
| GET | `/api/contracts/{id}/verifications` | Verification history |

## Data Files

The `data/` folder contains:
- `legal_references.xlsx`
- `risk_rules_master.xlsx`
- `test_set_labeled.xlsx`
- `sample_contracts/`

These files are reference/import data. They are not loaded automatically at startup.

## Notes

- Use `host.docker.internal` for backend container access to the host PostgreSQL container.
- DBeaver should still connect to `localhost:5432` because the database is published on the host.
- Keep `SECRET_KEY`, `DATABASE_URL`, and `CORS_ORIGINS` in `.env` for real deployments.
- Set `CORS_ORIGINS=*` if you want the API reachable from any browser origin on your LAN.
- The repo intentionally starts from an empty schema, not a preseeded database.
