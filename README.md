# MobyPark – Project Setup Guide

This document explains how to run the MobyPark backend API and the Elastic Stack (Elasticsearch + Kibana) locally for development.

## Prerequisites

### 1. Git

Used for verion control

- Windows: [Download Git for Windows](https://git-scm.com/download/win)
- Linux: sudo apt install git

### 2. Python 3.10+

Required to run the FastAPI backend.

- Check version: `python --version`

- Installation:
  - Windows: [Download Python](https://www.python.org/downloads/)
  - Linux: `sudo apt install python3 python3-pip`

### 3. Docker & Docker Compose

Required to run Elasticsearch and Kibana.

- Windows: Install Docker Desktop. Ensure Docker Desktop is running before continuing.
- Linux:
  ```
  sudo apt install docker docker-compose
  sudo systemctl start docker
  sudo systemctl enable docker
  ```
  (Optional: run `sudo usermod -aG docker $USER` to avoid using sudo for every command).

## Project Setup

### 1. Clone the repository

`git clone https://github.com/SadSayner/MobyPark-group1.git`

`cd MobyPark-group1`

### 2. Install Python dependencies

(Optional but recommended: use a virtual environment)

python -m venv venv

Activate it:

Windows

venv\Scripts\activate

Linux / macOS

source venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Make sure uvicorn is installed:

pip install "uvicorn[standard]"

### 3. Database migration

Migratie: bedrijven aanmaken voor gebruikers met meerdere voertuigen
Dit script maakt automatisch bedrijven aan voor gebruikers met meerdere voertuigen en koppelt hun voertuigen als bedrijfsauto’s.

Uitvoeren met:

sqlite3 v1/Database/MobyPark.db < v1/Database/migrations/add_companies_for_multi_vehicle_users.sql

Migratie uitvoeren zonder sqlite3 CLI
Wanneer sqlite3 niet beschikbaar is in de console kan de migratie worden uitgevoerd met:

python v1/Database/run_migration.py

### 4. Docker and docker compose

Start Elasticsearch and Kibana using Docker Compose:

docker compose up -d

Verify containers are running:

docker ps

Access services:

Elasticsearch: http://localhost:9200

Kibana: http://localhost:5601

Docker Desktop must be running on Windows, otherwise Docker will fail to connect.

Starting the FastAPI Backend (Uvicorn)

The API is NOT started via Docker yet.
You must start it manually using uvicorn.

From the project root directory:

uvicorn v1.server.routers.server:app --host 0.0.0.0 --port 8000 --reload

API endpoints:

API root: http://localhost:8000

Swagger UI: http://localhost:8000/docs

Health check: http://localhost:8000/health

Logging & Observability

The backend writes structured logs

Logs are collected by Filebeat

Logs are stored in Elasticsearch

Logs can be viewed in Kibana → Discover

Kibana setup:

Go to http://localhost:5601

Open Discover

Create an index pattern: v1

Select @timestamp as the time field
If you get no logs it means the @timestamp is wrong, you can safely remove it and you will be able to see all the logs

Stopping Everything
Stop FastAPI

Press:

CTRL + C

Stop Docker containers
docker compose down

Common Problems
Docker error on Windows:
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified

➡ Docker Desktop is not running

Port 8000 not reachable

Check if uvicorn is running

Verify command path: v1.server.routers.server:app

Notes

This setup is development-only

No authentication/security is enabled for Elasticsearch
