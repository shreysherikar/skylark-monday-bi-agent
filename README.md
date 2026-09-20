# Skylark Drones — Monday.com Business Intelligence Agent

[![Live Hosted Prototype](https://img.shields.io/badge/AWS%20ECS%20Express-Live%20Prototype-success?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://sk-72ae323ccddd4e948e038d970204cd22.ecs.ap-south-1.on.aws/)
[![Tests](https://img.shields.io/badge/Tests-169%20Passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python%203.11-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript%20%7C%20Vite-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Monday.com](https://img.shields.io/badge/Integration-Monday.com%20GraphQL%20v2%20%7C%20Connect%20Boards-6C5CE7?style=flat&logo=mondaydotcom&logoColor=white)](https://developer.monday.com)
[![MCP](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-blueviolet?style=flat)](https://modelcontextprotocol.io)

Conversational Business Intelligence (BI) Copilot integrating directly with **Monday.com Work Orders & Deals boards** via a read-only Model Context Protocol (MCP) server. Delivers deterministic business metrics, cross-board commercial risk analytics, evidence provenance trails, and transparent data quality caveats.

---

## Quick Start (5 Lines)

```bash
git clone https://github.com/shreysherikar/skylark-monday-bi-agent.git && cd skylark-monday-bi-agent
cp .env.example .env # Configure MONDAY_API_TOKEN, board IDs, and GROQ_API_KEY
pip install -e backend/
npm install --prefix frontend && npm run build --prefix frontend
python -m uvicorn app.main:app --app-dir backend --port 8000
```
* **Live Hosted URL**: [https://sk-72ae323ccddd4e948e038d970204cd22.ecs.ap-south-1.on.aws/](https://sk-72ae323ccddd4e948e038d970204cd22.ecs.ap-south-1.on.aws/)
* **Interactive OpenAPI Docs**: `http://localhost:8000/docs` | **System Health**: `http://localhost:8000/health`
* **Rate Limiting**: Public `/api/chat` is protected by a sliding-window rate limiter (60 requests/min per IP).

> **Dataset Horizon Notice**: Source CRM records extend historically through early 2026. Queries for *"this quarter"* (Q2 FY26-27) correctly return an empty-period response, transparently explaining the dataset boundary and surfacing nearest historical quarters (`FY25-26 Q4`, `Q3`, `Q2`).

---

## Architectural Principles

1. **Deterministic Analytics Over LLM Arithmetic**: The LLM is strictly an orchestrator for intent classification and natural language synthesis. 100% of financial totals, pipeline conversions, date boundary math, and cross-board risk checks run in typed Python analytics functions.
2. **In-Process MCP Integration**: The MCP server is fully implemented and tested under official MCP SDK contracts (`get_work_orders`, `get_deals`, `get_schema`). Runtime calls invoke its functions in-process to eliminate subprocess spawn latency (~300ms) and operational overhead while preserving strict schema boundaries.
3. **Enterprise Data Resilience**: Normalizes 71 free-text PO quantity formats, preserves negative customer credit balances, extracts Excel serial dates, and isolates 4 orthogonal status dimensions before analytics execute.
4. **Deterministic Date Resolution**: Slices dates in Indian Standard Time (`UTC+05:30`) against the Indian Fiscal Year (April 1 – March 31). Relative quarters ("this quarter") default to Indian FY deterministically.
5. **Transparent Governance Caveats**: Distinguishes unbilled/uncollected (`null`) from zero (`₹0`), highlights unrecorded deal values (52% null in raw deals), and refuses mathematically uncomputable metrics like DSO.

---

## Verified Runtime Architecture

```
User (Browser / REST Client)
  │
  ▼
React 18 Copilot Interface (ChatMessage.tsx)
  │ HTTPS / REST (JSON)
  ▼
FastAPI Gateway (/api/chat, /api/overview, /api/quality, /api/cross-board)
  │ (Protected by 60 req/min sliding-window rate limiter)
  ▼
Agent Orchestrator (orchestrator.py)
  ├── 1. Ambiguity & Clarification Decision Tree (clarification.py)
  │
  ├── 2. Deterministic Tool Dispatcher (tools.py)
  │        │
  │        ▼ (In-process call to MCP functions)
  │      Monday.com Read-Only MCP Server (monday_mcp/server.py)
  │        ├── Official Python MCP SDK Boundary (get_work_orders, get_deals, get_schema)
  │        ├── In-Memory 5-min TTL Cache & Pagination
  │        └── Pre-Transmission Mutation Defense (client.py)
  │        │
  │        ▼
  │      Monday.com GraphQL API v2 (api.monday.com/v2)
  │
  ├── 3. Normalization & Deterministic Analytics Engine (data/analytics.py)
  │        ├── 71 PO Quantity Cleaners & 4 Status Enums
  │        ├── Date Resolution in IST (data/date_resolver.py)
  │        ├── Revenue & Bookings (by PO date)
  │        ├── Sales Pipeline & Calibrated Win Rate: Won / (Won + Dead)
  │        └── Cross-Board Delivery Alignment (native Monday Connect Boards)
  │
  ├── 4. Structured Response Assembly (agent/structured_response.py)
  │        └── Builds StructuredCopilotResponse (summary, kpis, risks, evidence, caveats, follow_ups)
  │
  ├── 5. Compact Tool Output for LLM Turn (orchestrator.py)
  │        └── Groq SDK (openai/gpt-oss-120b) with rate-limit exponential backoff
  │
  ▼
ChatResponse Payload (Structured JSON + Synthesized Executive Markdown)
```

---

## Structured Copilot Responses & Evidence Traceability

Analytical responses attach a deterministic structured response contract to `/api/chat`:

```json
{
  "summary": "Total booked scope is {BOOKED_SCOPE} (Excl. GST) across {WORK_ORDER_COUNT} work orders. Billed amount is {BILLED_REVENUE} (Excl. GST), with net receivables of {NET_RECEIVABLES} after accounting for {CREDIT_ACCOUNT_COUNT} customer credit balances.",
  "kpis": [
    {
      "label": "Total Booked Scope (Excl. GST)",
      "value": "{BOOKED_SCOPE}",
      "context": "Across {WORK_ORDER_COUNT} work orders (by PO date)"
    },
    {
      "label": "Win Rate",
      "value": "51.0%",
      "context": "103 won / 202 decided deals (Open/On Hold excluded)"
    },
    {
      "label": "Current Outstanding Receivables",
      "value": "{NET_RECEIVABLES}",
      "context": "Gross: {GROSS_RECEIVABLES} (Credit balances: {CREDIT_TOTAL})"
    }
  ],
  "risks": [
    {
      "title": "Unclosed Deal Execution Risk",
      "detail": "{RISK_ORDER_COUNT} work order(s) totaling {RISK_VALUE} Excl GST are executing against non-won deals.",
      "severity": "high"
    }
  ],
  "evidence": {
    "sources": ["Monday.com Deals Board", "Monday.com Work Orders Board"],
    "records_analyzed": 520,
    "data_coverage": "15 of 176 Work Orders linked natively (8.5% coverage)",
    "calculation": "Deterministic Python aggregation via compute_pipeline_summary & date_resolver"
  },
  "caveats": [
    "Collection Date and Expected Billing Month are 100% null; DSO and invoice aging cannot be computed.",
    "Deal value is unrecorded for 179 of 344 deals (52.0%)."
  ],
  "follow_ups": [
    "Show me contract value leakage between Deals and Work Orders",
    "List the unclosed work orders with active execution"
  ]
}
```

---

## Core Capabilities & Technical Highlights

### 1. Cross-Board Intelligence (Deals ↔ Work Orders)
* **Confirmed Native Linkage**: Exactly **15 of 176 Work Orders (8.5%)** have confirmed relations to Deals on Monday.com via `Connect Boards`. Unmatched records are reported as unlinked with zero heuristic guessing.
* **Commercial Risk on Unclosed Deals**: Identifies work orders actively executed or completed for proposals that are still `Open`, `On Hold`, or `Dead` (e.g. project `SDPLDEAL-099` totaling ₹14.39M linked to an Open proposal).
* **Contract Value Leakage**: Pinpoints orders where delivery scope exceeded signed CRM deal commitments (6 projects with leakage totaling ₹114.7M).
* **Won Deals Backlog**: Identifies 96 Won deals (out of 103 total) with zero linked work orders on Monday.com, representing ₹101.9M in unbooked pipeline backlog.

### 2. Deterministic Business-Metric Computation
* `get_pipeline_summary`: Unweighted vs. probability-weighted pipeline, stage distribution, sector breakdowns, calibrated win rate (`Won / (Won + Dead)`), and top deal sales owners.
* `get_revenue_summary`: Bookings (by PO date), all-time billed and collected values, gross/net receivables, credit balances, and operations BD/KAM rankings.
* `get_cross_board_delivery`: Alignment between Work Orders and Deals (`view="summary" | "unclosed_deal_risk" | "value_variance" | "won_without_wo" | "alignment"`).
* `get_leadership_update`: Executive briefing combining pipeline, revenue bookings, delivery health, and governance caveats with temporal parameterization.
* `get_data_quality_report`: Null rates, GST tolerance checks, and bookkeeping flags.

### 3. Real-World Dirty Data Resilience
* **71 Free-Text PO Quantity Formats**: Normalizes mixed units (`HA`, `Acres`, `KM`, `MW`, `towers`, `days`, `sites`) and classifies non-numeric entries (`L/s`, `Rate based on MW slabs`).
* **Preservation of Legitimate Negative Balances**: Retains 11 customer credit accounts (negative receivables totaling -₹160.24k) and 6 negative billing adjustments, preventing margin distortion.
* **Blank ≠ Zero Accounting**: Missing monetary fields are tracked as `null` rather than zero.
* **GST 18% Mathematical Tolerance**: Reconciles `Incl ≈ Excl * 1.18` within ±₹0.50 margin across 175 rows.
* **Dynamic Header Filtering**: Filters repeated embedded header rows (indices 52 and 181 in Deals), tolerating raw or pre-cleaned sheets either way.

### 4. Deterministic Clarification Engine
* Relative phrases like *"this quarter"* default deterministically to the active Indian FY quarter in IST without modal interruptions.
* Vague queries (e.g. *"recently"*) generate dynamic selection chips computed from the current date.
* Automatically aggregates `"Renewables"` and `"Powerline"` when queries reference `"energy"`.
* Ranks Deals CRM Sales Owners and Work Orders BD/KAM Personnel in independent namespaces to reflect separate functional scopes.

---

## Tech Stack

| Domain | Technology | Justification |
| :--- | :--- | :--- |
| **LLM Reasoning** | Groq SDK (`openai/gpt-oss-120b`) | Structured tool calling with deterministic compact tool payloads and exponential backoff retry |
| **MCP Server** | Python `mcp` SDK + Monday.com GraphQL v2 | Schema-aware read-only board introspection and data extraction (3 public tools) |
| **Backend API** | FastAPI (Python 3.11+) | Asynchronous, typed REST endpoints with automatic OpenAPI documentation and sliding-window rate limiting (60 req/min) |
| **Data Engine** | Pandas & Pydantic v2 | Explicit data normalization, validation, deterministic date resolution, and analytics |
| **Frontend UI** | React 18, Vite 5, TypeScript | Responsive dashboard with glassmorphism styling, structured response cards, and live telemetry |
| **Cloud Hosting** | AWS ECS Express Mode (AWS Fargate) + Amazon ECR | Hosted container deployment in AWS `ap-south-1` |
| **Testing** | Pytest, AnyIO, Ruff | 169 offline unit/integration tests, strict typing, zero linter errors |

---

## Known Limitations

1. **Live Board Linkage Coverage**: Exactly 15 of 176 Work Orders (8.5%) have populated `Connect Boards` links on Monday.com. The agent explicitly caveats that cross-board delivery metrics represent matched records only.
2. **Bookings vs. Revenue Time-Slicing**: Work Orders filtered by date represent Bookings (by PO date). Billed and collected amounts cannot be time-sliced by quarter because billing and collection month columns are 100% unpopulated in Monday.com.
3. **DSO Impossibility**: Days Sales Outstanding (DSO) and invoice aging cannot be computed from source data because collection dates and billing months are 100% null. The agent explicitly refuses to fabricate estimates.
4. **Deals Data Gaps in Source Board**: `Close Date (A)` is 92.4% null (only 26 dates recorded out of 344), `Closure Probability` is 75.0% null, and `Masked Deal value` is 52.0% null. All pipeline summaries explicitly report these completeness percentages.
5. **Public API Rate Limiting**: The public `/api/chat` endpoint is rate-limited to 60 requests/minute per IP to prevent upstream Groq token quota exhaustion.

---

## Repository Structure

```
skylark-monday-bi-agent/
├── PROJECT_PLAN.md                  # Comprehensive engineering design & audit specification
├── DECISION_LOG.md                  # Architectural trade-offs, assumptions, and limitations (4 sections)
├── NORMALIZATION_NOTES.md           # Column-by-column audit and regex parsing rules
├── README.md                        # Project documentation and quick start
├── .env.example                     # Environment template (keys strictly excluded from git)
│
├── .github/
│   └── workflows/
│       ├── ci.yml                   # GitHub Actions automated test workflow
│       └── deploy.yml               # Automated test gate and AWS ECS deployment workflow
│
├── docs/
│   └── ARCHITECTURE_NOTES.md        # Technical appendix: schemas, ADRs 1–10, and test baselines
│
├── backend/
│   ├── pyproject.toml               # Python dependencies, pytest, and ruff configuration
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint, sliding-window rate limiter, and REST routes
│   │   ├── config.py                # Pydantic Settings environment configuration
│   │   ├── agent/
│   │   │   ├── orchestrator.py      # Groq LLM tool loop, compact payloads, and rate-limit backoff
│   │   │   ├── structured_response.py # Deterministic StructuredCopilotResponse builders
│   │   │   ├── tools.py             # Deterministic tool schemas and dispatchers
│   │   │   └── clarification.py     # Deterministic query ambiguity decision tree
│   │   ├── monday_mcp/
│   │   │   ├── client.py            # Read-only GraphQL client with pre-transmission mutation shields
│   │   │   ├── server.py            # MCP server tools (get_work_orders, get_deals, get_schema)
│   │   │   └── schema.py            # Dynamic schema introspection and mapping
│   │   └── data/
│   │       ├── date_resolver.py     # Deterministic Indian FY date resolution in IST
│   │       ├── normalize_work_orders.py  # Work orders cleaning and unit extraction
│   │       ├── normalize_deals.py        # Deals cleaning and funnel stage hierarchy
│   │       ├── analytics.py              # Mathematical aggregations & cross-board logic
│   │       └── quality_report.py         # Null-rate governance and caveat generators
│   └── tests/
│       ├── conftest.py              # Pytest configuration and offline stubbing fixture
│       ├── test_date_resolver.py    # Indian FY calendar and relative quarter tests
│       ├── test_structured_response.py # Unit tests for structured copilot response builders
│       ├── test_monday_mcp.py       # MCP server tool registration, cache, and mutation rejection
│       ├── test_monday_live.py      # Explicit live Monday.com verification suite
│       └── ...                      # Subsystem unit tests
│
├── frontend/                        # React 18 + Vite 5 TypeScript web application
│   ├── src/
│   │   ├── App.tsx                  # Root layout with sidebar navigation and view switcher
│   │   ├── api.ts                   # Typed API client for FastAPI backend
│   │   ├── types.ts                 # Domain models, TypeScript contracts, StructuredResponse
│   │   ├── components/              # Response cards, KPI grid, risk badges, evidence audit dock
│   │   └── views/                   # Overview, Funnel, Delivery, Quality, Chat views
│   └── package.json
│
├── infra/
│   └── Dockerfile                   # Multi-stage container build (Vite frontend + FastAPI)
│
└── scripts/
    ├── build_deal_links.py          # Multi-feature offline Deal ↔ Work Order matcher
    ├── deal_wo_links.csv            # Ground-truth link seed mapping
    └── monday_board_setup.md        # Monday.com board setup and CSV import guide
```

---

## Monday.com Board Configuration

To connect your Monday.com workspace:

1. **Work Orders Board**:
   * Create a board named `Work Orders`.
   * Import `Work_Order_Tracker Data.xlsx` (Row 1 is empty; configure Row 2 as column headers).
   * Map monetary columns to **Numbers** and status columns to **Status / Dropdown**.
2. **Deals Board**:
   * Create a board named `Deals`.
   * Import `Deal funnel Data.xlsx` (The agent dynamically filters repeated header rows at runtime, tolerating raw or pre-cleaned sheets either way).
   * Map `Masked Deal value` to **Numbers**; map `Deal Stage`, `Deal Status`, and `Closure Probability` to **Status / Dropdown**.
3. **Cross-Board Connect Boards Column**:
   * On `Work Orders`, add a **Connect Boards** column named `Linked Deal` connected to `Deals`.
   * *(One-Time Setup)*: Native links on the sample board were populated once externally using `scripts/deal_wo_links.csv`. The agent is strictly read-only and never writes to Monday.com.

---

## Automated Testing & Verification

Normal tests run 100% offline using deterministic mock fixtures without depending on external credentials:

```bash
cd backend

# Run offline deterministic CI test suite (169 passed, 5 deselected in ~13s):
python -m pytest

# Run live Monday.com integration verification (requires MONDAY_API_TOKEN):
python -m pytest -m live

# Code linting:
python -m ruff check .
```

**Test Verification Breakdown (169 Tests):**
* `test_date_resolver.py` (8 tests): Indian FY quarter boundaries, relative quarters, bare quarters, and fallback parsing.
* `test_analytics.py` (18 tests): Deterministic arithmetic, temporal filtering, bookings label, calibrated win rate, owner breakdowns, and DSO refusal.
* `test_structured_response.py` (12 tests): Structured Copilot response models, builders, evidence provenance, risk tagging, error fallback.
* `test_normalize_work_orders.py` (47 tests): 71 mixed PO unit variations, negative credit balances, Excel serial date epochs, 4 null columns.
* `test_normalize_deals.py` (12 tests): Embedded header row cleaning, 16-stage pipeline hierarchy sorting, sector aliasing.
* `test_monday_mcp.py` (23 tests): MCP server tools, resources, read-only mutation defense, pagination, concurrent 5-minute TTL cache, schema introspection.
* `test_monday_live.py` (5 tests): Live board verification (176 Work Orders, 344 Deals, 15 Connect Board relations).
* `test_clarification.py` (6 tests): Indian Fiscal Year default, relative timeframes, and dynamic suggested options.
* `test_agent_orchestrator.py` (11 tests): Groq tool loop, compact tool payload formatting, rate-limit retry backoff, currency sanitization.
* `test_agent_tools.py` (12 tests): Tool argument validation, period dispatching, cross-board delivery view filtering.
* `test_api_chat.py` (13 tests): FastAPI request lifecycle, sliding-window rate limiting (60 req/min), structured response forwarding.
* `test_deal_matching.py` (7 tests): Deterministic multi-feature cross-board resolution engine.

---

## Example Conversational Prompts

In the conversational interface or via `/api/chat`:

1. **Flagship Temporal Pipeline Query (Dataset Boundary & Historical Benchmark)**:
   > *"How's our pipeline for the energy sector this quarter?"*
   *(Explains that Q2 FY26-27 has 0 deals and surfaces FY26-27 Q1 and FY25-26 Q4/Q3/Q2 historical activity).*
2. **Calibrated Win-Rate Query**:
   > *"What is our win rate for closed deals and how is it calculated?"*
   *(Reports 51.0% Win Rate based on 103 Won / 202 decided deals, excluding Open and On Hold).*
3. **DSO & Aging Refusal Policy**:
   > *"What is our Days Sales Outstanding (DSO) and invoice aging breakdown?"*
   *(Refuses to fabricate estimates, stating collection dates and billing months are 100% null).*
4. **Cross-Board Governance & Commercial Risk**:
   > *"Are we executing any work orders on deals that haven't been won yet?"*
5. **Contract Value Leakage**:
   > *"Show me contract value variance between sales CRM commitments and work orders."*
6. **Receivables & Customer Credit Accounts**:
   > *"What is our net vs. gross accounts receivable position, and do we have any customer credit balances?"*
7. **Executive Leadership Briefing**:
   > *"Give me an executive leadership update."*
8. **Data Quality & Governance Audit**:
   > *"Generate a data quality report and tell me which columns have severe null rates."*

---

## Submission Export & Secrets Hygiene

To export a clean, evaluation-ready ZIP bundle without risking exposure of local `.env` files:

```bash
# Export only git-tracked files into submission ZIP (strictly excludes .env and .env.*)
git archive -o skylark-submission.zip HEAD
```
