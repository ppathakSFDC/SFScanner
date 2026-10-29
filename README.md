# SF Scanner — Salesforce Best Practice Analyzer

AI-powered web tool that connects to any Salesforce org, scans components for violations,
and suggests Claude-powered fixes.

## What it scans

| Component | Rules | Key Checks |
|---|---|---|
| **Apex** | 9 | SOQL/DML in loops, missing sharing, empty catch, hardcoded IDs |
| **Flow** | 7 | DML in loops, no fault paths, filters missing, unreachable elements |
| **OmniScript** | 7 | Step count, caching, error handling, nested sub-scripts |
| **DataRaptor** | 6 | SELECT *, no filters, Turbo Extract opportunity |
| **Integration Procedure** | 6 | HTTP timeouts, error handling, DR in loops, parallelism |
| **Pricing Procedure** | 5 | Hardcoded prices, complexity, unused variables |
| **Business Rules** | 5 | Condition count, duplicate rules, hardcoded IDs, priority |

## Setup

### 1. Salesforce Connected App

Create a Connected App in your Salesforce org:
- **Callback URL**: `http://localhost:8000/auth/callback`
- **OAuth Scopes**: `api`, `refresh_token`, `offline_access`
- Note the **Consumer Key** and **Consumer Secret**

### 2. Configure environment

```bash
cd backend
cp .env.example .env
# Edit .env with your values:
# SF_CLIENT_ID=<Consumer Key>
# SF_CLIENT_SECRET=<Consumer Secret>
# ANTHROPIC_API_KEY=<your key from console.anthropic.com>
# SESSION_SECRET=<random string>
```

### 3. Run

```bash
chmod +x start.sh
./start.sh
```

Open **http://localhost:5173** and click "Connect Salesforce Org".

## Architecture

```
sf-scanner/
├── backend/                  # FastAPI
│   ├── main.py               # App entry point
│   ├── config.py             # Settings from .env
│   ├── auth/oauth.py         # Salesforce OAuth 2.0 flow
│   ├── salesforce/client.py  # Tooling + REST API client
│   ├── scanners/             # One module per component type
│   │   ├── apex_scanner.py
│   │   ├── flow_scanner.py
│   │   ├── omniscript_scanner.py
│   │   ├── dataraptor_scanner.py
│   │   ├── integration_procedure_scanner.py
│   │   ├── pricing_procedure_scanner.py
│   │   └── business_rules_scanner.py
│   ├── ai/analyzer.py        # Claude API enrichment + summaries
│   ├── routers/              # FastAPI route handlers
│   └── models/findings.py    # Pydantic data models
└── frontend/                 # React + Vite
    └── src/
        ├── pages/Login.jsx
        ├── pages/Dashboard.jsx   # Scan launcher + history
        └── pages/ScanReport.jsx  # Interactive findings report
```

## Scan Report Features

- **Summary tiles**: total components, findings by severity
- **Sidebar filters**: filter by severity (Critical/High/Medium/Low) or component type
- **Search**: full-text search across findings
- **Expandable cards**: click any finding to see:
  - AI root-cause explanation
  - Current code snippet
  - Suggested fix (diff format)
  - Fix effort estimate
 
  ## Launch App
  - Click on launch.command to launch the app
