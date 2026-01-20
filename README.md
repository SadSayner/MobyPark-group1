# MobyPark-group1

### Migratie: bedrijven aanmaken voor gebruikers met meerdere voertuigen

Dit script maakt automatisch bedrijven aan voor gebruikers met meerdere
voertuigen en koppelt hun voertuigen als bedrijfsauto’s.

Uitvoeren met:

sqlite3 v1/Database/MobyPark.db < v1/Database/migrations/add_companies_for_multi_vehicle_users.sql

### Migratie uitvoeren zonder sqlite3 CLI

Wanneer sqlite3 niet beschikbaar is in de console kan de migratie worden uitgevoerd met:

python v1/Database/run_migration.py

## End-to-end (E2E) tests

The E2E tests start the real FastAPI app using `uvicorn` in a subprocess and make real HTTP requests against it.

### 1) Create & activate a virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
```

### 2) Install dependencies

This repo does not currently ship a `requirements.txt`, so install the minimum needed packages:

```powershell
python -m pip install -U pip
python -m pip install pytest uvicorn fastapi pydantic bcrypt
```

Notes:
- Elasticsearch logging is optional. The E2E tests disable it automatically.
- If you see a message about `email-validator`, it’s optional.

### 3) Run the E2E tests

From the repo root:

```powershell
python -m pytest e2e -v -s
```

### Environment variables (optional)

The E2E harness sets these automatically for reliable local runs:

- `MOBYPARK_SKIP_SEED=1` (skips heavy database seeding on startup)
- `MOBYPARK_DISABLE_ELASTIC_LOGS=1` (prevents Elasticsearch logging from blocking startup)

If you want to test with full startup behavior, you can run with them unset (startup may take significantly longer).
