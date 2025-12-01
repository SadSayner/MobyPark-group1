# MobyPark Command Reference

Quick reference for all commands to run the MobyPark application.

---

## 🗄️ Database Commands

### Create/Recreate Database
```bash
cd v1
python Database/database_creation.py
```

### Delete Database
```bash
cd v1
rm Database/MobyPark.db
```

### Load Data from JSON Files
```bash
cd v1
python storage_utils.py
```

---

## 🚀 Start the Server

### Start FastAPI Server (with auto-reload)
```bash
cd v1
python -m uvicorn server.app:app --reload
```

### Start Server (without auto-reload)
```bash
cd v1
python -m uvicorn server.app:app
```

### Start Server on Different Port
```bash
cd v1
python -m uvicorn server.app:app --reload --port 8080
```

### Start Server with Host Binding (accessible from network)
```bash
cd v1
python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

**Access URLs when server is running:**
- API Root: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health Check: http://127.0.0.1:8000/health

---

## 🧪 Testing Commands

### Run Comprehensive Test (Detailed Output)
```bash
cd v1
python tests/test_with_testclient.py
```
**Best for:** Debugging, seeing detailed responses

### Run Pytest Suite (Quick Summary)
```bash
cd v1
pytest tests/test_endpoints.py -v
```
**Best for:** Quick validation, CI/CD

### Run Pytest with Output
```bash
cd v1
pytest tests/test_endpoints.py -v -s
```
Shows print statements during tests

### Run Specific Test Class
```bash
cd v1
pytest tests/test_endpoints.py::TestAuthentication -v
```

### Run Specific Test
```bash
cd v1
pytest tests/test_endpoints.py::TestAuthentication::test_login_success -v
```

### Run Pytest with Coverage
```bash
cd v1
pytest tests/test_endpoints.py --cov=server --cov-report=html
```
Creates coverage report in `htmlcov/index.html`

### Stop at First Failure
```bash
cd v1
pytest tests/test_endpoints.py -x
```

### Show Local Variables on Failure
```bash
cd v1
pytest tests/test_endpoints.py -l
```

---

## 🔧 Development Workflow

### Full Reset and Test
```bash
cd v1
# 1. Delete old database
rm Database/MobyPark.db

# 2. Create fresh database
python Database/database_creation.py

# 3. Load your data
python storage_utils.py

# 4. Run tests
python tests/test_with_testclient.py
```

### Quick Development Cycle
```bash
cd v1
# Start server in one terminal
python -m uvicorn server.app:app --reload

# In another terminal, run tests
pytest tests/test_endpoints.py -v
```

---

## 📦 Package Management

### Install Dependencies
```bash
pip install fastapi uvicorn sqlite3 pydantic
```

### Install Testing Dependencies
```bash
pip install pytest pytest-cov
```

### List Installed Packages
```bash
pip list
```

### Freeze Requirements
```bash
pip freeze > requirements.txt
```

### Install from Requirements
```bash
pip install -r requirements.txt
```

---

## 🔍 Debugging Commands

### Check Database Tables
```bash
cd v1
python -c "import sqlite3; con = sqlite3.connect('Database/MobyPark.db'); print([t[0] for t in con.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()])"
```

### Check Database Schema
```bash
cd v1
python -c "import sqlite3; con = sqlite3.connect('Database/MobyPark.db'); print(con.execute('SELECT sql FROM sqlite_master WHERE type=\"table\" AND name=\"users\"').fetchone()[0])"
```

### Count Records in Table
```bash
cd v1
python -c "import sqlite3; con = sqlite3.connect('Database/MobyPark.db'); print('Users:', con.execute('SELECT COUNT(*) FROM users').fetchone()[0])"
```

### View All Users
```bash
cd v1
python -c "import sqlite3; con = sqlite3.connect('Database/MobyPark.db'); con.row_factory = sqlite3.Row; [print(dict(row)) for row in con.execute('SELECT * FROM users').fetchall()]"
```

---

## 📁 File Operations

### Check if Data Files Exist
```bash
cd v1
ls -la data/
```

### View Data File
```bash
cd v1
cat data/users.json
```

### Edit Data File (Windows)
```bash
cd v1
notepad data/users.json
```

### Edit Data File (VS Code)
```bash
cd v1
code data/users.json
```

---

## 🔄 Git Commands (if using version control)

### Check Status
```bash
git status
```

### Add Changes
```bash
git add .
```

### Commit Changes
```bash
git commit -m "Description of changes"
```

### Push to Remote
```bash
git push
```

### Pull Latest Changes
```bash
git pull
```

---

## 🛠️ Common Workflows

### First Time Setup
```bash
# 1. Navigate to project
cd C:\Users\Frank\SCPT-MobyPark\MobyPark-group1\v1

# 2. Create database
python Database/database_creation.py

# 3. Edit data files
code data/users.json
code data/parking-lots.json

# 4. Load data
python storage_utils.py

# 5. Run tests
python tests/test_with_testclient.py

# 6. Start server
python -m uvicorn server.app:app --reload
```

### Daily Development
```bash
cd v1

# Option 1: Test-driven development
python tests/test_with_testclient.py  # Run tests
# Make changes to code
python tests/test_with_testclient.py  # Run tests again

# Option 2: Server-based development
python -m uvicorn server.app:app --reload  # Start server
# Test using http://127.0.0.1:8000/docs
# Server auto-reloads when you save changes
```

### Before Committing Code
```bash
cd v1

# 1. Run all tests
pytest tests/test_endpoints.py -v

# 2. Check coverage
pytest tests/test_endpoints.py --cov=server

# 3. Format code (if using formatter)
# black . --check

# 4. Commit if all pass
git add .
git commit -m "Your commit message"
git push
```

### Troubleshooting
```bash
cd v1

# Delete everything and start fresh
rm Database/MobyPark.db
rm -rf __pycache__
rm -rf server/__pycache__
rm -rf Database/__pycache__

# Recreate
python Database/database_creation.py
python storage_utils.py
python tests/test_with_testclient.py
```

---

## 🆘 Emergency Commands

### Kill Server (if stuck)
```bash
# Windows
taskkill /F /IM python.exe

# Or press Ctrl+C in the terminal where server is running
```

### Clear Python Cache
```bash
cd v1
find . -type d -name __pycache__ -exec rm -rf {} +
```

### Reset Everything
```bash
cd v1
rm Database/MobyPark.db
rm -rf __pycache__ server/__pycache__ Database/__pycache__
python Database/database_creation.py
python tests/test_with_testclient.py
```

---

## 📝 Quick Reference Table

| Task | Command |
|------|---------|
| Start server | `python -m uvicorn server.app:app --reload` |
| Run comprehensive test | `python tests/test_with_testclient.py` |
| Run pytest | `pytest tests/test_endpoints.py -v` |
| Create database | `python Database/database_creation.py` |
| Load data | `python storage_utils.py` |
| View Swagger docs | http://127.0.0.1:8000/docs |
| Stop server | `Ctrl+C` |
| Delete database | `rm Database/MobyPark.db` |

---

## 💡 Pro Tips

1. **Always run commands from `v1/` directory**
2. **Use `--reload` during development** (auto-restart on code changes)
3. **Run tests before committing** code
4. **Use pytest for quick validation**
5. **Use test_with_testclient.py for debugging**
6. **Check http://127.0.0.1:8000/docs** to see all endpoints
7. **Keep one terminal for server, one for tests**

---

## 🔗 URLs When Server is Running

| Service | URL |
|---------|-----|
| API Root | http://127.0.0.1:8000 |
| Swagger UI (Interactive) | http://127.0.0.1:8000/docs |
| ReDoc (Documentation) | http://127.0.0.1:8000/redoc |
| Health Check | http://127.0.0.1:8000/health |
| OpenAPI JSON | http://127.0.0.1:8000/openapi.json |
