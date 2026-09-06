# Web-Weebforce - Contract Verifier

Contract Verifier is a full-stack app for:
- uploading contract files
- verifying SHA-256 integrity
- managing contract clauses
- importing legal reference data and risk rules from Excel

This repo is designed to run with:
- PostgreSQL, backend and frontend running together in Docker Compose
- optional data import from the `data/` folder

## Project Layout

```text
backend/                  FastAPI backend
frontend/                 React/Vinext frontend
data/                     Excel references and sample contracts
docker-compose.yml        PostgreSQL + backend + frontend stack
.env.example              Environment template
```

## What Runs Automatically

- The backend creates the database schema on startup.
- Backend startup waits for the PostgreSQL healthcheck to pass.
- Schema creation uses SQLAlchemy `create_all` plus missing indexes. There is no
  versioned migration runner; existing table definitions are not upgraded automatically.
- No users, contracts, or verification logs are seeded automatically.
- Sample/reference data is imported only when you run the import job manually.

## Prerequisites

- Docker Desktop

## Database Setup

Compose creates the `postgres` service and the database named by `POSTGRES_DB`.
Backend and the optional importer connect to `postgres:5432` on the Compose
network using `DATABASE_URL`. No separately installed PostgreSQL is needed.

Database files persist in the named volume `postgres-data`. PostgreSQL initializes
the user/password/database only when that volume is empty; changing `.env` later
does not change credentials in an existing database. `docker compose down` retains
the volume; `docker compose down -v` deletes its data.

Port 5432 is not published to the host. For optional DBeaver access, explicitly add
`127.0.0.1:5432:5432` to the postgres service's `ports`, then connect to localhost.

## Quick Start with cmd

1. Copy `.env.example` to `.env`
```bash
copy .env.example .env
```
2. Set a development-only password in the ignored `.env`. Keep the password in
`POSTGRES_PASSWORD` and `DATABASE_URL` consistent. URL-encode special characters
in the URL password. Never commit `.env`.

```env
POSTGRES_USER=admin
POSTGRES_PASSWORD=replace_with_local_password
POSTGRES_DB=contract_verifier_db
DATABASE_URL=postgresql://admin:replace_with_local_password@postgres:5432/contract_verifier_db
CORS_ORIGINS=*
BACKEND_INTERNAL_URL=http://backend:8000
```

3. Validate without printing credentials, then start the three services:

```bash
docker compose config --quiet
docker compose up -d --build postgres backend frontend
```

4. Open the app:
- Frontend: `http://localhost:3000`
- Backend health check: `http://localhost:8000/health`
- Backend health check through frontend proxy: `http://localhost:3000/health`

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
- `postgres`: PostgreSQL 17 with healthcheck and persistent storage
- `backend`: FastAPI API
- `frontend`: web UI
- `import-data`: manual seed/import job

The backend and importer both use `DATABASE_URL` from the environment and wait for
the `postgres` service to become healthy. Normal startup does not run the `seed` profile.

## Frontend Behavior

The frontend proxies API requests to the backend container, so you can use the app from a single origin in Docker.

If you run frontend and backend separately, set:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

If you run through Docker Compose, you can leave `NEXT_PUBLIC_API_BASE_URL` empty.

## Local Dev Without Docker

If you want to run only the backend locally:

Provide a reachable PostgreSQL instance and set `DATABASE_URL` in the shell.
The Compose hostname `postgres` is only resolvable inside its Docker network.
Backend does not automatically load the root `.env` when run directly.

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

- Use `postgres:5432` for database access from backend/importer containers.
- Keep `SECRET_KEY`, `DATABASE_URL`, and `CORS_ORIGINS` in `.env` for real deployments.
- Set `CORS_ORIGINS=*` if you want the API reachable from any browser origin on your LAN.
- The repo intentionally starts from an empty schema, not a preseeded database.
