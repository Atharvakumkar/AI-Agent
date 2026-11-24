# SentinelAI

SentinelAI is a cross-platform server health monitoring and controlled remediation application built with FastAPI, React, LangGraph, Groq, `psutil`, and SQLite.

It monitors local Windows and Ubuntu Linux systems while a dashboard session is active, detects threshold-based resource anomalies, investigates root causes using a tool-calling AI agent, and executes allowlisted remediation actions only after explicit user approval and post-action verification.

---

## Architecture

SentinelAI follows a modular monolith architecture with strict separation between telemetry collection, anomaly evaluation, AI investigation, safety-guarded remediation, persistence, and presentation.

- **Monitoring Engine (`backend/app/monitoring/`)**: Collects CPU, RAM, swap, disk, OS metadata, uptime, and process metrics via `psutil`, isolating OS-specific mount filtering and protected process lists inside `WindowsAdapter` and `LinuxAdapter`.
- **Anomaly Detection Engine (`backend/app/anomalies/`)**: Evaluates snapshots against configurable warning/critical thresholds with per-key cooldown suppression, immediate `WARNING` to `CRITICAL` escalation, and automatic recovery resets.
- **LangGraph AI Agent (`backend/app/agent/`)**: Runs a bounded ReAct-style tool-calling loop on Groq using 7 read-only diagnostic tools, followed by a structured synthesis node that separates confirmed tool observations from suspected causes.
- **Controlled Remediation Engine (`backend/app/remediation/`)**: Enforces human-in-the-loop approval, allowlist-only dispatch, OS protected-process blocklists, PID reuse verification, and pre/post metric verification.
- **FastAPI & SQLite Layer (`backend/app/api/`, `backend/app/db/`)**: Exposes REST endpoints and a session-scoped WebSocket stream (`/ws/metrics`) that starts polling when a dashboard connects and stops cleanly when all clients disconnect.
- **React Dashboard (`frontend/src/`)**: TypeScript + Vite single-page interface providing live Recharts telemetry graphs, process inspection, threshold configuration, investigation reports, remediation approval controls, and an incident audit log.

## Technology Stack

| Layer | Technology |
| :--- | :--- |
| Frontend | React, TypeScript, Vite, Recharts |
| Backend | Python 3.12, FastAPI, Uvicorn |
| AI Agent | LangGraph, LangChain Core, Groq API |
| System Telemetry | `psutil` with Windows and Linux OS adapters |
| Database | SQLite with SQLAlchemy 2.0 ORM |
| Testing | `pytest`, FastAPI `TestClient` |

## Directory Structure

```text
sentinelai/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangGraph workflow, 7 read-only tools, prompts, report schemas
│   │   ├── anomalies/      # Threshold rules, cooldown deduplication, severity classifier
│   │   ├── api/            # REST routers, WebSocket session manager, shared dependencies
│   │   ├── db/             # SQLAlchemy engine, ORM models, repository CRUD layer
│   │   ├── monitoring/     # Cross-platform psutil collector, Windows & Linux adapters
│   │   ├── remediation/    # Allowlist registry, safety guards, handlers, metric verifier
│   │   ├── config.py       # Typed environment configuration via pydantic-settings
│   │   └── main.py         # FastAPI application entrypoint and lifespan hooks
│   ├── scripts/
│   │   └── load_simulator.py  # Controlled multi-core CPU and memory spike generator
│   ├── tests/              # Unit, security, cross-platform, and API integration tests
│   ├── .env.example
│   ├── pytest.ini
│   └── requirements.txt
└── frontend/
    └── src/
        ├── components/     # SystemOverview, ResourceCharts, ProcessTable, AlertsPanel,
        │                   # InvestigationReport, RemediationModal, IncidentHistory
        ├── services/       # Typed REST client and WebSocket stream hook
        ├── styles/         # Dashboard stylesheet
        └── types/          # Shared TypeScript API and telemetry interfaces
```

---

## Security and Safety Controls

### 1. No Arbitrary Shell Execution

The LLM outputs a structured `RemediationProposal` restricted to an enum allowlist:

- `terminate_process`
- `restart_managed_service`
- `clear_temp_directory`
- `none`

### 2. Explicit User Authorization

Proposed actions remain in `PENDING` state in SQLite until approved via:

`POST /api/remediation/{id}/decide`

### 3. OS Protected Process Blocklists

Critical Windows processes (`System`, `csrss.exe`, `wininit.exe`, `lsass.exe`, `svchost.exe`, etc.) and Linux processes (`systemd`, `init`, `sshd`, `dbus-daemon`, `dockerd`, etc.) are blocked even if an approved request targets them.

### 4. PID Reuse Protection

Process termination verifies that the live OS process name at `target_pid` still matches the `target_name` observed during investigation.

### 5. Verified Outcomes Only

Every executed action:

1. Captures pre-action metrics.
2. Waits for OS counters to settle.
3. Re-samples live metrics.
4. Records whether the issue is verified resolved (`VERIFIED_RESOLVED`) or unresolved (`EXECUTED_UNRESOLVED`).

---

## Local Setup

### Prerequisites

- Python 3.12
- Node.js and npm
- Git
- Groq API key
- Windows 11 or Ubuntu Linux

### 1. Backend Setup

#### Windows (PowerShell)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

#### Ubuntu Linux (Bash)

```bash
cd backend
python3 -m venv .venv-linux
source .venv-linux/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Configure Environment Variables

Edit `backend/.env` and configure your Groq API key:

```env
GROQ_API_KEY=your_actual_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

### 2. Frontend Setup

Open a second terminal from the project root:

```bash
cd frontend
npm install
```

---

## Running the Project

SentinelAI requires two independently running services: the FastAPI backend and the React frontend.

### Step 1: Start the Backend

Open a terminal, navigate to `backend/`, activate your virtual environment, and execute:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend will be available at:

- **API Base URL:** `http://127.0.0.1:8000`
- **Interactive API Documentation:** `http://127.0.0.1:8000/docs`

### Step 2: Start the Frontend

Open another terminal, navigate to `frontend/`, and execute:

```bash
npm run dev
```

The frontend will be available at:

`http://localhost:5173`

### Step 3: Open the Dashboard

Open `http://localhost:5173` in your browser.

Once the dashboard connects to the backend through its WebSocket session:

- Live system monitoring begins.
- CPU, RAM, swap, and disk metrics are collected.
- Running processes are displayed.
- Resource utilization is visualized through live charts.
- Threshold-based anomaly detection becomes active.

Monitoring automatically stops when all dashboard clients disconnect.

### Step 4: Monitor System Resources

Navigate through the dashboard to inspect:

- System overview and resource utilization.
- CPU and memory usage graphs.
- Disk and swap utilization.
- Running processes and their resource consumption.
- Protected OS processes.
- Active alerts and historical incidents.

### Step 5: Trigger an AI Investigation

When an anomaly is detected:

1. Navigate to **Alerts & AI Agent**.
2. Select the relevant alert.
3. Click **Investigate**.
4. Allow the LangGraph agent to execute its read-only diagnostic tools.
5. Review the generated investigation report.

The report separates confirmed system observations from suspected root causes.

### Step 6: Execute Controlled Remediation

If the AI agent proposes a remediation action:

1. Review the proposed action.
2. Inspect the target process and risk level.
3. Review the remediation rationale.
4. Click **Approve & Execute** to authorize the action.
5. Allow the remediation engine to execute its safety checks.
6. Review the post-action verification results.

The system records whether the action successfully resolved the detected issue.

### Step 7: Review Incident History

Navigate to **Incident History** to inspect persisted records containing:

- Original anomaly details.
- AI investigation reports.
- Proposed remediation actions.
- User approval or rejection decisions.
- Safety guard results.
- Post-action verification metrics.

---

## Testing

### Run Automated Tests

From the `backend/` directory with your virtual environment activated:

```bash
pytest -v
```

The test suite covers:

- Unit testing.
- Anomaly detection.
- Security and remediation safeguards.
- Cross-platform monitoring.
- API integration.
- FastAPI endpoint behavior.

### Simulate CPU Usage

To generate a controlled CPU spike:

```bash
python scripts/load_simulator.py --mode cpu --duration 45
```

### Simulate Memory Usage

To generate a controlled memory spike:

```bash
python scripts/load_simulator.py --mode memory --duration 45
```

These simulations can be used to test threshold-based anomaly detection and AI investigation workflows.

---

## Core API Endpoints

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| GET | `/health` | Service status and host OS metadata |
| WS | `/ws/metrics` | Session-scoped real-time telemetry and anomaly stream |
| GET | `/api/metrics/snapshot` | On-demand point-in-time system snapshot |
| GET / PUT | `/api/metrics/thresholds` | View or update anomaly detection thresholds |
| GET | `/api/alerts` | Retrieve persisted anomaly records |
| POST | `/api/agent/investigate` | Trigger a LangGraph AI investigation by anomaly ID or prompt |
| GET | `/api/remediation/pending` | List remediation actions awaiting user approval |
| POST | `/api/remediation/{id}/decide` | Approve or reject a proposed remediation action |
| GET | `/api/incidents` | Retrieve full incident, report, and remediation audit history |

---

## Final Verification and Git Commit

### 1. Confirm Repository Status

Run from the `sentinelai/` project root:

```powershell
git status
```

Verify that the following files and directories are ignored by Git:

- `.env`
- `*.db`
- `venv/`
- `.venv-linux/`
- `backend/runtime/`
- `frontend/node_modules/`

### 2. Run Backend Tests

```powershell
cd backend
pytest -v
```

### 3. Build the Frontend

```powershell
cd ..\frontend
npm run build
```

### 4. Return to Project Root

```powershell
cd ..
```

### 5. Commit the Project to Git

Stage all project files:

```powershell
git add .
```

Commit the changes:

```powershell
git commit -m "feat: complete SentinelAI monitoring, LangGraph agent, guarded remediation, dashboard, and docs"
```

---

## Project Summary

| Component | Implementation |
| :--- | :--- |
| Project Name | SentinelAI |
| Architecture | Modular Monolith |
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| AI Agent | LangGraph, LangChain Core, Groq |
| System Monitoring | psutil |
| Database | SQLite, SQLAlchemy |
| Operating Systems | Windows and Ubuntu Linux |
| Testing | pytest, FastAPI TestClient |
| Communication | REST API and WebSockets |

**SentinelAI — Intelligent Monitoring. Controlled Remediation. Verified Outcomes.**