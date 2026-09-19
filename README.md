# Skylark Drones — Monday.com Business Intelligence Agent

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Monday.com](https://img.shields.io/badge/Integration-Monday.com%20GraphQL%20v2-6C5CE7?style=flat&logo=mondaydotcom&logoColor=white)](https://developer.monday.com)
[![Tests](https://img.shields.io/badge/Tests-130%20Passed-brightgreen?style=flat&logo=pytest&logoColor=white)](https://pytest.org)
[![Architecture](https://img.shields.io/badge/Architecture-Deterministic%20BI%20%2B%20MCP-blueviolet?style=flat)](#architecture-overview)

> An enterprise-grade Conversational Business Intelligence (BI) copilot that integrates directly with **Monday.com Work Orders & Deals boards** via a read-only Model Context Protocol (MCP) server. Built to ingest, normalize, and reason across messy real-world operational and sales pipeline data with **zero arithmetic hallucinations** and **mandatory data-governance caveats**.

---

## Executive Overview

Executive leadership and founders often need immediate, reliable answers across fragmented operational systems:
* *"How is our pipeline looking for the energy sector this quarter?"*
* *"What is our gross vs. net accounts receivable position, taking customer credit balances into account?"*
* *"Give me this week's executive leadership update."*

Answering these traditionally demands hours of manual spreadsheet reconciliation, custom CSV cleaning, and interpreting incomplete records. General-purpose LLMs fail at this because **they calculate arithmetic in their heads**—hallucinating plausible-sounding totals over dirty real-world datasets.

**Skylark BI Agent solves this with strict architectural separation:**
1. **The LLM is strictly an orchestrator**: It interprets intent, detects ambiguity, selects deterministic tools, and narrates findings.
2. **Arithmetic is 100% deterministic**: All sums, probability weightings, credit allocations, and cross-board fulfillment metrics are computed in typed Python analytics engines.
3. **Data resilience is first-class**: Free-text mixed PO units, negative credit balances, Excel serial epochs, and severe null rates are cleanly handled before anything reaches the business layer.
4. **Transparency over false confidence**: Every metric carries live governance caveats (e.g., distinguishing unbilled/uncollected from zero, and highlighting unrecorded deal values).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Enterprise Frontend Canvas (React 18 + TS)               │
│   • Conversational Intelligence Chat        • Dynamic KPI Telemetry Cards   │
│   • Funnel Velocity & Stage Breakdowns      • Fulfillment & Receivables View│
│   • Global Command Palette (⌘K / Ctrl+K)    • Real-Time Null-Rate Warnings  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTPS / REST (JSON)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                  Agent API & Reasoning Gateway (FastAPI)                    │
│   • Ambiguity Decision Tree (§8) — Clarification prompting & suggested chips│
│   • Tool-Use Autonomous Loop (Groq Open-Weights SDK: gpt-oss-120b / Llama-3)│
│   • Currency Sanitization (Strict ₹ / INR symbol normalization)             │
└───────────────┬──────────────────────────────────────────────┬──────────────┘
                │ Deterministic Tool Calls                     │ Deterministic Tool Calls
┌───────────────▼──────────────┐             ┌─────────────────▼──────────────┐
│  Monday.com Read-Only MCP    │             │   Data Normalization &         │
│  • Official Python MCP SDK   │             │   Resilience Engine (§9)       │
│  • GraphQL v2 Client         │             │   • Mixed PO Unit Parser       │
│  • In-Memory 5-min TTL Cache │             │   • Negative Value Accounting  │
│  • Mutation Security Shields │             │   • 4 Orthogonal Status Fields │
│  • Schema Introspection      │             │   • Header Cleaning & GST 18%  │
└───────────────┬──────────────┘             └─────────────────┬──────────────┘
                │ GraphQL Queries                              │ DataFrames
┌───────────────▼──────────────────────────────────────────────▼──────────────┐
│                         Monday.com Cloud Boards                              │
│   • Work Order Tracker Board (176 projects, 38 schema columns)               │
│   • Deal Funnel Tracker Board (344 valid deals, 16-stage pipeline)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Technical Highlights

### 1. Zero-Arithmetic-Hallucination Guarantee
The reasoning engine is strictly prohibited from computing numbers internally. When a user asks for pipeline figures, receivables, or cross-board delivery, the agent invokes dedicated, unit-tested analytical tools:
* `get_pipeline_summary`: Unweighted vs. probability-weighted pipeline, stage distribution, sector breakdowns.
* `get_revenue_summary`: Bookings, billed revenue (Excl/Incl GST), collected funds, and net vs. gross receivables.
* `get_cross_board_delivery`: Alignment between Work Orders and Deals using live Monday.com `Connect Boards` relations.
* `get_leadership_update`: Automated executive briefing combining revenue, delivery health, pipeline velocity, and audit risks.
* `get_data_quality_report`: Real-time null rates, GST sanity checks, and bookkeeping flags.

### 2. Enterprise Data Resilience & Normalization
The underlying real-world datasets contain significant messiness. The normalization layer resolves these explicitly:
* **71 Free-Text PO Quantity Variations**: Extracts numeric floats alongside normalized unit strings (`HA`, `Acres`, `KM`, `RKM`, `MW`, `towers`, `days`, `months`, `images`, `sites`, `mines`), while classifying qualitative lump-sum entries (`L/s`, `Rate based on MW slabs`).
* **Preservation of Legitimate Negative Balances**:
  * **11 Customer Credit Accounts** (negative `Amount Receivable`, min −₹160.24) representing client overpayments and credit notes—never clamped to zero.
  * **6 Negative Billing Rows** in `Amount to be billed` representing execution volume adjustments.
  * **2 Negative Balance Quantities** where executed volume exceeded estimates.
* **Blank ≠ Zero Accounting**: Missing monetary fields are tracked as `null` (unbilled / uncollected), preventing severe margin distortions.
* **4 Orthogonal Status Dimensions**: Prevents conflation of `Execution Status` (fulfillment), `Invoice Status` (billing), `WO Status (billed)` (ERP account closure), and `Billing Status` (exception handling).
* **GST 18% Tolerance Check**: Reconciles `Incl ≈ Excl * 1.18` within a ±₹0.50 margin across 175 rows.
* **Duplicate Header Cleaning**: Filters embedded header repetitions in Deals, yielding exactly 344 valid records.

### 3. Read-Only MCP Integration Layer
* Built with the official Python `mcp` SDK.
* Enforces read-only operations at the code level: defensive regex blocks any `mutation` operation before network dispatch.
* Cursor-based pagination smoothly fetches high-volume boards without hitting complexity budget limits.
* In-memory thread-safe TTL cache (5-minute expiration) satisfies the assignment's dynamic query mandate while avoiding API rate limits.

### 4. Deterministic Clarification Engine
Queries with ambiguous parameters automatically trigger clarifying questions with interactive selection buttons:
* **Time Boundary Ambiguity**: When a user asks about *"this quarter"*, the agent asks whether to evaluate against the **Indian Fiscal Year (Q4 FY25-26: Jan–Mar)**, **Calendar Year (Q1: Jan–Mar)**, or **All-Time**.
* **Vague Horizon Ambiguity**: Prompts like *"recently"* or *"past few months"* request specific date windows.
* **Sector Aliasing**: Automatically maps terms like *"energy"* or *"solar"* to the board's standard `"Renewables"` sector.

---

## Tech Stack

| Domain | Technology | Purpose |
| :--- | :--- | :--- |
| **LLM Reasoning** | Groq Python SDK (`openai/gpt-oss-120b` / `llama-3.3-70b-versatile`) | High-speed, cost-effective open-weights tool-use orchestration |
| **MCP Server** | Python `mcp` SDK | Structured, schema-aware read-only board introspection and retrieval |
| **Backend API** | FastAPI (Python 3.11+) | Asynchronous, typed REST endpoints with automatic OpenAPI validation |
| **Data Engine** | Pandas & Pydantic v2 | Explicit data normalization, validation, and deterministic analytics |
| **Frontend UI** | React 18, Vite 5, TypeScript | Responsive single-page application with custom glassmorphism design |
| **UI Components** | Lucide React, React Markdown, Remark GFM | Native Markdown briefing rendering and rich iconography |
| **Testing** | Pytest, Pytest-Cov, AnyIO | 130 unit and integration tests with strict coverage thresholds |
| **Containerization** | Docker, AWS App Runner / Render | Production-ready multi-stage deployment packaging |

---

## Repository Structure

```
skylark-monday-bi-agent/
├── PROJECT_PLAN.md                  # Detailed engineering spec and design calibration
├── DECISION_LOG.md                  # Architectural trade-offs, assumptions, and limitations
├── NORMALIZATION_NOTES.md           # Comprehensive column-by-column audit and parsing rules
├── README.md                        # Project documentation and setup guide
│
├── backend/
│   ├── pyproject.toml               # Python dependencies and build metadata
│   ├── app/
│   │   ├── main.py                  # FastAPI server entrypoint and route handlers
│   │   ├── config.py                # Environment configuration (Pydantic Settings)
│   │   ├── agent/
│   │   │   ├── orchestrator.py      # LLM tool-calling loop and currency sanitization
│   │   │   ├── tools.py             # Deterministic tool schemas and dispatchers
│   │   │   └── clarification.py     # Deterministic query ambiguity decision tree
│   │   ├── monday_mcp/
│   │   │   ├── client.py            # Read-only GraphQL client with mutation shields
│   │   │   ├── server.py            # MCP tools (get_work_orders, get_deals, get_schema)
│   │   │   └── schema.py            # Dynamic schema introspection and mapping
│   │   └── data/
│   │       ├── normalize_work_orders.py  # Work orders cleaning and unit extraction
│   │       ├── normalize_deals.py        # Deals cleaning and funnel stage hierarchy
│   │       ├── analytics.py              # Mathematical aggregations & leadership reports
│   │       └── quality_report.py         # Null-rate governance and caveat generators
│   └── tests/                       # 130 comprehensive unit and integration tests
│
├── frontend/                        # React 18 + Vite 5 single-page application
│   ├── src/
│   │   ├── App.tsx                  # Root layout with sidebar and view switcher
│   │   ├── api.ts                   # Typed API client for FastAPI backend
│   │   ├── types.ts                 # Domain models and TypeScript contracts
│   │   ├── components/              # Chat input, messages, top nav, command palette
│   │   └── views/                   # Overview, Funnel, Delivery, and Quality dashboards
│   └── package.json
│
├── infra/
│   ├── Dockerfile                   # Container definition for cloud deployment
│   └── apprunner.yaml               # AWS App Runner deployment specification
│
└── scripts/
    ├── build_deal_links.py          # Multi-feature offline Deal ↔ Work Order matcher
    └── monday_board_setup.md        # Monday.com board setup and CSV import guide
```

---

## Monday.com Board Configuration

To import the source datasets into Monday.com boards and configure the integration:

1. **Work Orders Board**:
   * Create a new board named `Work Orders`.
   * Import `Work_Order_Tracker Data.xlsx` (Note: Row 1 is empty; set Row 2 as column headers).
   * Ensure `Amount in Rupees (Excl of GST)`, `Billed Value`, and `Amount Receivable` are mapped to **Numbers** columns.
   * Ensure `Execution Status`, `Invoice Status`, and `Sector` are mapped to **Status / Dropdown** columns.
2. **Deals Board**:
   * Create a new board named `Deals`.
   * Import `Deal funnel Data.xlsx` (Filter out rows 52 and 181, which contain repeated header rows).
   * Map `Masked Deal value` to a **Numbers** column.
   * Map `Deal Stage`, `Deal Status`, and `Closure Probability` to **Status / Dropdown** columns.
3. **Cross-Board Connection**:
   * On the `Work Orders` board, add a **Connect Boards** column named `Linked Deal`.
   * Link it to the `Deals` board to enable live cross-board fulfillment queries.

For detailed column-by-column mapping specifications, refer to [`scripts/monday_board_setup.md`](scripts/monday_board_setup.md).

---

## Setup & Local Development

### Prerequisites
* **Python**: 3.11 or higher
* **Node.js**: 18 or higher (with npm)
* **Monday.com API Token**: Personal API Token from Monday.com Developer section
* **Groq API Key**: Free API key from [console.groq.com](https://console.groq.com)

### 1. Environment Configuration
Create a `.env` file in the root directory:
```bash
MONDAY_API_TOKEN="your_monday_personal_api_token"
MONDAY_WORK_ORDERS_BOARD_ID="5031416769"
MONDAY_DEALS_BOARD_ID="5031416803"
GROQ_API_KEY="gsk_your_groq_api_key"
GROQ_MODEL="openai/gpt-oss-120b"
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at `http://localhost:8000/docs`.

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Access the web application at `http://localhost:5173`.

---

## Running Automated Tests

The test suite covers data normalization edge cases, MCP caching, clarification decision trees, and API endpoints:
```bash
cd backend
python -m pytest tests/ -v
```

**Test Breakdown (130 Tests Passing):**
* `test_normalize_work_orders.py`: 47 tests (mixed PO units, negative credit amounts, Excel dates, 4 null columns).
* `test_normalize_deals.py`: 12 tests (repeated header elimination, 16-stage funnel sorting, sector cleaning).
* `test_analytics.py`: 12 tests (deterministic sums, weighted pipeline calculations, credit account balances).
* `test_monday_mcp.py`: 12 tests (read-only mutation rejection, cursor pagination, 5-min TTL cache, schema introspection).
* `test_clarification.py`: 6 tests (ambiguous quarter handling, vague time intervals, suggested chip generation).
* `test_agent_orchestrator.py`: 11 tests (Groq tool-use loop, prompt construction, currency sanitization).
* `test_agent_tools.py`: 11 tests (tool argument schemas and execution dispatchers).
* `test_api_chat.py`: 12 tests (FastAPI request lifecycle, `/health`, `/api/chat`, error handling).
* `test_deal_matching.py`: 7 tests (deterministic multi-feature cross-board resolution engine).

---

## Deployment

The application is containerized and ready for deployment on **AWS App Runner**, **Render**, or any container platform.

### Docker Build & Run Locally
```bash
docker build -t skylark-bi-agent -f infra/Dockerfile .
docker run -p 8000:8000 --env-file .env skylark-bi-agent
```

### Deploying to AWS App Runner
1. Authenticate with Amazon ECR and push the container image:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   docker tag skylark-bi-agent:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/skylark-bi-backend:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/skylark-bi-backend:latest
   ```
2. Create an App Runner service pointing to the ECR image with `PORT=8000` and inject the environment variables via AWS Secrets Manager.
