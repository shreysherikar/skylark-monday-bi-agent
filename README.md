# Skylark Drones — Monday.com BI Agent

A conversational Business Intelligence agent for executive leadership, connecting read-only to Monday.com boards (Work Orders and Deals) via MCP. Built to handle messy real-world data with resilience, explicit normalization, and data-quality caveats.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Single-Page Chat UI)                         │
│  - Next.js (React) / Streamlit                          │
└───────────────────────┬─────────────────────────────────┘
                         │ HTTPS
┌───────────────────────▼─────────────────────────────────┐
│  Agent API (FastAPI, Python)                            │
│  - Orchestrates Claude (Anthropic API) via tool-use     │
│  - Query parsing, ambiguity clarification, response     │
│    composition with data-quality caveats                │
└───────┬───────────────────────────────┬─────────────────┘
        │ tool calls                    │ tool calls
┌───────▼────────────┐        ┌─────────▼─────────────┐
│ Monday MCP client  │        │ Normalization &       │
│ (read-only queries │        │ Analytics Layer       │
│ via GraphQL)       │        │ (pandas, typed models)│
└───────┬────────────┘        └─────────┬─────────────┘
        │                               │
┌───────▼───────────────────────────────▼─────────────────┐
│  Monday.com Boards (Work Orders, Deals)                 │
│  - Single source of truth, dynamically queried          │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Reasoning Engine**: Anthropic Claude API (tool use / function calling)
- **MCP Server**: Python official `mcp` SDK over Monday.com GraphQL API
- **Backend API**: FastAPI (Python 3.11+)
- **Data & Normalization**: Pandas, Pydantic v2
- **Frontend**: Next.js / Streamlit
- **Hosting**: AWS App Runner (backend) + AWS Amplify / S3 (frontend)
- **CI/CD**: GitHub Actions

## Repository Structure

```
├── PROJECT_PLAN.md              # Engineering spec and calibration guidelines
├── DECISION_LOG.md              # Architectural decisions, trade-offs, and assumptions
├── NORMALIZATION_NOTES.md       # Column-by-column data audit and normalization rules
├── README.md                    # Setup and architecture overview
├── .github/workflows/
│   ├── ci.yml                   # Linting, typing, and unit tests
│   └── deploy.yml               # Automated build and deployment
├── backend/
│   ├── pyproject.toml           # Python dependencies and tool configuration
│   ├── app/
│   │   ├── main.py              # FastAPI application entrypoint
│   │   ├── config.py            # Application configuration & env vars
│   │   ├── agent/               # Claude orchestration & clarification
│   │   ├── monday_mcp/          # MCP server & Monday.com GraphQL client
│   │   └── data/                # Normalization, quality reporting & analytics
│   └── tests/                   # Pytest test suite & synthetic fixtures
├── frontend/                    # Web chat interface
├── infra/                       # Dockerfile & AWS App Runner configuration
└── scripts/                     # Board setup and ingestion guides
```

## Setup & Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- Monday.com API token
- Anthropic API key

### Backend Setup
```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
