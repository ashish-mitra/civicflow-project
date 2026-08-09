# CivicFlow — An Open Innovation Hackathon Project

CivicFlow is a full-stack civic issue reporting and resolution platform. Citizens can report local problems, attach details, track progress, and see what is happening in their area. A lightweight operations dashboard lets civic teams triage, assign, and update issues.

## Problem
Local problems such as potholes, broken streetlights, overflowing bins, water leaks and unsafe public spaces are often reported through fragmented channels. Citizens rarely know whether a complaint was received, who owns it, or when it will be fixed.

## Solution
One transparent workflow:
1. Citizen reports an issue with category, location and description.
2. CivicFlow creates a trackable ticket and assigns a priority using simple rules.
3. The operations team changes status, adds an assignee and records an update.
4. Citizens see live progress and resolution metrics.

## Stack
- FastAPI + SQLite backend
- Vanilla HTML/CSS/JavaScript frontend
- Responsive, accessible UI
- REST API for reports, dashboard stats and status updates

## Run
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```
Open http://127.0.0.1:8000

## API
- `GET /api/issues`
- `POST /api/issues`
- `GET /api/issues/{id}`
- `PATCH /api/issues/{id}`
- `GET /api/stats`

The database is created automatically and seeded with demo records on first run.
