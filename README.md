# MobyPark

MobyPark is a parking management system built with FastAPI, providing RESTful APIs for managing parking lots, vehicles, reservations, and sessions.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Windows](#windows)
  - [Linux](#linux)
- [Running the Application](#running-the-application)
  - [Using Docker (Recommended)](#using-docker-recommended)
  - [Monitoring Logs](#monitoring-logs)
- [Testing](#testing)
  - [End-to-End Tests](#end-to-end-tests)
- [Database Migrations](#database-migrations)
- [API Documentation](#api-documentation)

## Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software

- **Git** - Version control system
- **Python 3.9+** - Programming language runtime
- **Docker** - Container platform

### Windows

1. **Git**
   - Download and install from [git-scm.com](https://git-scm.com/download/win)
   - Or use `winget`:
     ```powershell
     winget install Git.Git
     ```

2. **Python**
   - Download and install from [python.org](https://www.python.org/downloads/)
   - Or use `winget`:
     ```powershell
     winget install Python.Python.3.12
     ```
   - Make sure to check "Add Python to PATH" during installation

3. **Docker Desktop**
   - Download and install from [docker.com](https://www.docker.com/products/docker-desktop/)
   - Requires Windows 10/11 64-bit with WSL 2
   - Start Docker Desktop after installation

### Linux

1. **Git**
   ```bash
   # Debian/Ubuntu
   sudo apt update
   sudo apt install git

   # Fedora
   sudo dnf install git

   # Arch
   sudo pacman -S git
   ```

2. **Python**
   ```bash
   # Debian/Ubuntu
   sudo apt update
   sudo apt install python3 python3-pip python3-venv

   # Fedora
   sudo dnf install python3 python3-pip

   # Arch
   sudo pacman -S python python-pip
   ```

3. **Docker**
   ```bash
   # Debian/Ubuntu
   sudo apt update
   sudo apt install docker.io docker-compose
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo usermod -aG docker $USER

   # Fedora
   sudo dnf install docker docker-compose
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo usermod -aG docker $USER

   # Arch
   sudo pacman -S docker docker-compose
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo usermod -aG docker $USER
   ```

   **Note:** After adding yourself to the docker group, log out and log back in for the changes to take effect.

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd MobyPark-group1
   ```

2. **Verify installations**
   ```bash
   git --version
   python --version  # or python3 --version on Linux
   docker --version
   docker compose version
   ```

## Running the Application

### Using Docker (Recommended)

1. **Build the Docker containers**
   ```bash
   docker compose build
   ```

   This command builds the Docker images defined in `docker-compose.yml`. This may take a few minutes on the first run.

2. **Start the application**
   ```bash
   docker compose up -d
   ```

   The `-d` flag runs the containers in detached mode (in the background). This will take a long time when there is no database.

3. **Verify the application is running**

   The API should now be available at:
   - **API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs (Swagger UI)
   - **Alternative API Documentation**: http://localhost:8000/redoc (ReDoc)

### Monitoring Logs

To view the startup logs and monitor the API in real-time:

```bash
docker compose logs -f api
```

Press `Ctrl+C` to stop following the logs (the containers will continue running).

### Managing the Application

**Stop the application:**
```bash
docker compose down
```

**Restart the application:**
```bash
docker compose restart
```

**View all running containers:**
```bash
docker compose ps
```

**Stop and remove all containers, networks, and volumes:**
```bash
docker compose down -v
```

## Testing

### End-to-End Tests

The E2E tests start the real FastAPI application using `uvicorn` in a subprocess and make real HTTP requests against it.

#### 1. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. Install test dependencies

```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install required packages
python -m pip install pytest uvicorn fastapi pydantic bcrypt
```

**Notes:**
- Elasticsearch logging is optional and disabled automatically during tests
- If you see a warning about `email-validator`, it's optional and can be ignored

#### 3. Run the E2E tests

From the repository root directory:

```bash
python -m pytest e2e -v -s
```

**Options:**
- `-v` - Verbose output (shows test names)
- `-s` - Show print statements and output

**Run specific test files:**
```bash
python -m pytest e2e/test_auth.py -v
```

**Run specific test:**
```bash
python -m pytest e2e/test_auth.py::test_register -v
```

#### Environment Variables

The E2E test harness automatically sets these environment variables for reliable local testing:

- `MOBYPARK_SKIP_SEED=1` - Skips database seeding on startup (faster tests)
- `MOBYPARK_DISABLE_ELASTIC_LOGS=1` - Prevents Elasticsearch logging from blocking startup

If you want to test with full startup behavior (including seeding), you can manually unset these variables, but be aware that startup may take significantly longer.

## Database Migrations

### Running Migrations

#### Option 1: Using SQLite CLI (if installed)

```bash
sqlite3 v1/Database/MobyPark.db < v1/Database/migrations/add_companies_for_multi_vehicle_users.sql
```

#### Option 2: Using Python Script

If `sqlite3` CLI is not available in your terminal:

```bash
python v1/Database/run_migration.py
```

### What Migrations Do

The current migration automatically creates companies for users with multiple vehicles and links their vehicles as company cars.

## API Documentation

Once the application is running, you can explore the API documentation:

- **Swagger UI**: http://localhost:8000/docs
  - Interactive API documentation
  - Test endpoints directly from the browser
  - Admin login: username: admin | password: password

- **ReDoc**: http://localhost:8000/redoc
  - Alternative, more readable documentation format

### Main API Endpoints

- **Authentication**: `/api/register`, `/api/login`, `/api/logout`
- **Vehicles**: `/api/vehicles`
- **Parking Lots**: `/api/parking-lots`
- **Sessions**: `/api/parking-lots/{id}/sessions/start`, `/api/parking-lots/{id}/sessions/stop`
- **Reservations**: `/api/reservations`
- **Admin**: `/api/admin/dashboard`, `/api/admin/users`

## Project Structure

```
MobyPark-group1/
├── v1/
│   ├── Database/          # Database files and migrations
│   ├── server/
│   │   ├── routers/       # API route handlers
│   │   ├── validation/    # Input validation
│   │   └── logging_config.py  # Logging configuration
│   └── storage_utils.py   # Storage utilities
├── e2e/                   # End-to-end tests
├── docker-compose.yml     # Docker configuration
├── Dockerfile            # Docker image definition
└── README.md             # This file
```

## Troubleshooting

### Docker Issues

**Problem**: `docker compose` command not found
- **Solution**: Use `docker-compose` (with hyphen) instead on older Docker versions

**Problem**: Permission denied on Linux
- **Solution**: Add your user to the docker group and log out/in:
  ```bash
  sudo usermod -aG docker $USER
  ```

**Problem**: Port 8000 already in use
- **Solution**: Stop the process using port 8000 or change the port in `docker-compose.yml`

**Problem**: API connection errors on port 8000 even when port is not in use by other applications
- **Solution**: Elasticsearch will take some time to start (can take up to 5 minutes), the api will not start until Elasticsearch is ready.

### Python/Test Issues

**Problem**: `python` command not found on Linux
- **Solution**: Use `python3` instead

**Problem**: Module not found errors during tests
- **Solution**: Ensure you've activated the virtual environment and installed all dependencies

**Problem**: Tests failing with connection errors
- **Solution**: Ensure no other instance of the application is running on port 8000