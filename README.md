# Skylark Drones — Monday.com Business Intelligence Agent

[![Live Hosted Prototype](https://img.shields.io/badge/AWS%20ECS%20Express-Live%20Prototype-success?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://sk-72ae323ccddd4e948e038d970204cd22.ecs.ap-south-1.on.aws/)
[![Tests](https://img.shields.io/badge/Tests-132%20Passed%20%7C%2094%25%20Coverage-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python%203.11-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript%20%7C%20Vite-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Monday.com](https://img.shields.io/badge/Integration-Monday.com%20GraphQL%20v2%20%7C%20Connect%20Boards-6C5CE7?style=flat&logo=mondaydotcom&logoColor=white)](https://developer.monday.com)
[![MCP](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-blueviolet?style=flat)](https://modelcontextprotocol.io)

> **Enterprise-Grade Conversational Business Intelligence (BI) Copilot** integrating directly with **Monday.com Work Orders & Deals boards** via a read-only Model Context Protocol (MCP) server. Engineered to ingest, normalize, and reason across real-world operational and sales pipeline data with **zero arithmetic hallucinations**, **deterministic cross-board risk analytics**, and **transparent data-governance caveats**.

---

## 🚀 Live Hosted Application

| Attribute | Details |
| :--- | :--- |
| **Production URL** | **[https://sk-72ae323ccddd4e948e038d970204cd22.ecs.ap-south-1.on.aws/](https://sk-72ae323ccddd4e948e038d970204cd22.ecs.ap-south-1.on.aws/)** |
| **Cloud Infrastructure** | **AWS ECS Express Mode (AWS Fargate)** in `ap-south-1` (Mumbai) |
| **Container Registry** | **Amazon Elastic Container Registry (ECR)** |
| **Deployment Mode** | Serverless Docker Container (FastAPI + React 18 SPA) |
| **API Health & Docs** | Interactive OpenAPI docs (`/docs`) and system telemetry (`/health`) |

---

## 🎯 Overview & Product Vision

Leadership and operations executives at drone technology enterprises like Skylark require rapid, verified visibility across sales and delivery operations:
* *"Give me this week's executive leadership update."*
* *"Are we executing work orders on deals that haven't actually been won yet?"*
* *"What is our contract value variance between sales CRM commitments and delivery bookings?"*
* *"What is our gross vs. net accounts receivable position, taking client credit balances into account?"*

Answering these questions across disparate Monday.com boards typically requires tedious spreadsheet exports, ad-hoc python scripts, and subjective guesswork. General-purpose LLMs fail here: **they compute arithmetic in their neural network parameters**, causing severe hallucinations, misaggregations, and false confidence over real-world datasets.

### Architectural Principles
1. **The LLM is Strictly an Orchestrator**: Uses open-weights models via the Groq SDK (`openai/gpt-oss-120b` or `llama-3.3-70b-versatile`) solely to parse user intent, detect semantic ambiguity, invoke backend tools, and narrate findings.
2. **100% Deterministic Arithmetic**: Every total, percentage, weighted pipeline calculation, credit balance reconciliation, and cross-board variance is calculated strictly in typed Python analytics engines.
3. **Enterprise Data Resilience**: Normalizes 71 free-text PO quantity units, preserves negative accounting credit balances, extracts Excel serial epochs, and isolates 4 orthogonal status dimensions before anything reaches the business layer.
4. **Transparent Governance Caveats**: Distinguishes unbilled/uncollected (`null`) from zero (`₹0`), highlights unrecorded deal values (52% null in raw deals), and quantifies live cross-board linkage coverage.

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                          Enterprise Frontend Canvas (React 18 + TS)                         │
│   • Conversational Intelligence Chat        • Dynamic KPI Telemetry Cards                   │
│   • Funnel Velocity & Stage Breakdowns      • Delivery & Cross-Board Alignment Matrix       │
│   • Global Command Palette (⌘K / Ctrl+K)    • Real-Time Data Governance Caveat Warnings     │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │ HTTPS / REST (JSON)
┌──────────────────────────────────────────────▼──────────────────────────────────────────────┐
│                          FastAPI Gateway & Reasoning Engine                                 │
│   • Ambiguity Decision Tree (§8) — Clarification prompts & interactive suggested chips      │
│   • Tool-Use Autonomous Loop (Groq Open-Weights SDK: gpt-oss-120b / Llama-3)                │
│   • Strict Currency Sanitization (₹ / INR formatting, non-breaking spaces)                  │
└───────────────────────┬──────────────────────────────────────────────┬──────────────────────┘
                        │ Deterministic Tool Invocation                │ Deterministic Tool Invocation
┌───────────────────────▼──────────────────────┐      ┌────────────────▼──────────────────────┐
│          Monday.com Read-Only MCP            │      │       Deterministic Analytics &       │
│   • Official Python MCP SDK                  │      │       Normalization Engine            │
│   • GraphQL v2 Client with Pagination        │      │   • 71 PO Quantity Unit Cleaners      │
│   • In-Memory Thread-Safe 5-min TTL Cache    │      │   • Customer Credit Reconciliation    │
│   • Mutation Security Regex Shields          │      │   • 4 Orthogonal Status Enums         │
│   • Dynamic Schema Introspection             │      │   • GST 18% Mathematical Sanity       │
└───────────────────────┬──────────────────────┘      └────────────────┬──────────────────────┘
                        │ GraphQL v2 Queries                           │ DataFrames
┌───────────────────────▼──────────────────────────────────────────────▼──────────────────────┐
│                                 Monday.com Cloud Boards                                     │
│   • Work Order Tracker Board (176 projects, 38 schema columns, Connect Boards)              │
│   • Deal Funnel Tracker Board (344 valid deals, 16-stage pipeline)                          │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Core Capabilities & Technical Highlights

### 1. Cross-Board Intelligence (Deals ↔ Work Orders)
Monday.com's native `Connect Boards` column (`Linked Deal`) links projects between the Deals and Work Orders boards. Our analytics engine queries these live relations to answer critical founder-level governance questions:
* **Commercial Risk on Unclosed Deals**: Identifies work orders being actively executed or completed for proposals that are still `Open`, `On Hold`, or `Dead`.
  * *Audit Result*: Discovered **5 work orders** totaling **₹20,838,860.24 Excl GST** linked to unclosed deals, including project `SDPLDEAL-099` (Ongoing, ₹14.39M) linked to an Open proposal (`Goku`).
* **Contract Value Leakage & Variance**: Compares CRM Deal Value against Work Order Booked Amount and Billed Revenue.
  * *Audit Result*: Discovered **6 projects with contract leakage** totaling **₹114,710,914.13**, where booked scope exceeded contracted CRM deal value.
* **Won Deals Backlog**: Identifies Closed-Won deals that have not yet had a corresponding delivery work order spun up.
  * *Audit Result*: **96 out of 103 Won Deals** have zero linked work orders on Monday.com, representing **₹101,899,594.90** in unbooked pipeline backlog.
* **Unlinked Execution Financial Exposure**: Detects work orders without CRM attribution (**161 orders** totaling **₹180M+** in execution).
* **Delivery View Alignment Matrix**: An interactive UI table in the web dashboard displaying linked deal names, stages, contract values, work order execution status, booked amounts, and automated risk badges with one-click audit prompt buttons.

### 2. Zero-Arithmetic-Hallucination Guarantee
The reasoning LLM never computes numbers internally. It dispatches typed queries to dedicated analytical tools:
* `get_pipeline_summary`: Unweighted vs. probability-weighted pipeline, stage distribution, sector breakdowns.
* `get_revenue_summary`: Bookings, billed revenue (Excl/Incl GST), collections, gross receivables (₹3,62,91,913.69), and net receivables (₹3,62,91,748.87).
* `get_cross_board_delivery`: Alignment between Work Orders and Deals via native Monday Connect Boards (`view="summary" | "unclosed_deal_risk" | "value_variance" | "won_without_wo" | "alignment"`).
* `get_leadership_update`: Automated executive briefing combining revenue, delivery health, pipeline velocity, and audit risks.
* `get_data_quality_report`: Real-time null rates, GST tolerance checks, and bookkeeping flags.

### 3. Real-World Dirty Data Resilience
* **71 Free-Text PO Quantity Formats**: Extracts numeric values and standardizes units across `HA`, `Acres`, `KM`, `RKM`, `MW`, `towers`, `days`, `months`, `images`, `sites`, `mines`, while classifying non-numeric lump-sum entries (`L/s`, `Rate based on MW slabs`).
* **Preservation of Legitimate Negative Balances**:
  * **11 Customer Credit Accounts** (negative `Amount Receivable`, min −₹160.24) representing client overpayments and credit balances—never clamped to zero.
  * **6 Negative Billing Adjustments** in `Amount to be billed` representing execution volume scope adjustments.
  * **2 Negative Balance Quantities** where executed volume exceeded estimates.
* **Blank ≠ Zero Accounting**: Missing monetary fields are tracked as `null` (unbilled / uncollected), preventing margin distortions.
* **4 Orthogonal Status Dimensions**: Separates `Execution Status` (fulfillment), `Invoice Status` (billing), `WO Status (billed)` (ERP account closure), and `Billing Status` (exception handling).
* **GST 18% Mathematical Tolerance**: Reconciles `Incl ≈ Excl * 1.18` within a ±₹0.50 margin across 175 rows.
* **Header Deduplication**: Eliminates embedded header rows (rows 52 and 181 in Deals), yielding exactly 344 valid deal records.

### 4. Read-Only MCP Integration Layer
* Built using the official Python `mcp` SDK.
* Enforces read-only operations: regex barriers reject any `mutation` operation before network transmission.
* Cursor-based pagination smoothly fetches high-volume boards without hitting complexity budget limits.
* Thread-safe in-memory 5-minute TTL cache satisfies dynamic query requirements without exhausting Monday.com rate limits.

### 5. Deterministic Clarification Engine
Queries with ambiguous parameters trigger clarifying questions with interactive selection chips:
* **Time Boundary Ambiguity**: When asked about *"this quarter"*, prompts whether to evaluate against **Indian Fiscal Year (Q4 FY25-26: Jan–Mar)**, **Calendar Year (Q1: Jan–Mar)**, or **All-Time**.
* **Vague Horizon Ambiguity**: Prompts like *"recently"* or *"past few months"* request specific date windows.
* **Sector Aliasing**: Automatically maps terms like *"energy"* or *"solar"* to the board's standard `"Renewables"` sector.

---

## 🛠️ Tech Stack

| Domain | Technology | Justification |
| :--- | :--- | :--- |
| **LLM Reasoning** | Groq SDK (`openai/gpt-oss-120b` / `llama-3.3-70b-versatile`) | Ultra-fast tool-calling loop (~500ms) with deterministic tool payload compaction |
| **MCP Server** | Python `mcp` SDK + Monday.com GraphQL v2 | Standardized, schema-aware read-only board introspection and data extraction |
| **Backend API** | FastAPI (Python 3.11+) | Asynchronous, typed REST endpoints with automatic OpenAPI documentation |
| **Data Engine** | Pandas & Pydantic v2 | Explicit data normalization, validation, and deterministic analytics |
| **Frontend UI** | React 18, Vite 5, TypeScript | High-performance dashboard with glassmorphism design and live telemetry |
| **3D WebGL Engine** | Three.js | Procedural 3D industrial quadcopter UAV, hover physics, and illuminated Earth operations globe |
| **Cloud Hosting** | AWS ECS Express Mode (AWS Fargate) + Amazon ECR | Production serverless containerization in AWS `ap-south-1` |
| **Testing** | Pytest, Pytest-Cov, AnyIO, Ruff, Mypy | 132 automated tests, 94.07% coverage, strict type checks |

---

## 📁 Repository Structure

```
skylark-monday-bi-agent/
├── PROJECT_PLAN.md                  # Comprehensive engineering design & audit specification
├── DECISION_LOG.md                  # Architectural trade-offs, assumptions, and limitations
├── NORMALIZATION_NOTES.md           # Column-by-column audit and regex parsing rules
├── README.md                        # Project documentation and setup guide
│
├── backend/
│   ├── pyproject.toml               # Python dependencies, pytest, and ruff configuration
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint, static mount, and REST routes
│   │   ├── config.py                # Pydantic Settings environment configuration
│   │   ├── agent/
│   │   │   ├── orchestrator.py      # Groq LLM tool-calling loop and currency sanitization
│   │   │   ├── tools.py             # Deterministic tool schemas and dispatchers
│   │   │   └── clarification.py     # Deterministic query ambiguity decision tree
│   │   ├── monday_mcp/
│   │   │   ├── client.py            # Read-only GraphQL client with mutation shields
│   │   │   ├── server.py            # MCP server tools (get_work_orders, get_deals, get_schema)
│   │   │   └── schema.py            # Dynamic schema introspection and mapping
│   │   └── data/
│   │       ├── normalize_work_orders.py  # Work orders cleaning and unit extraction
│   │       ├── normalize_deals.py        # Deals cleaning and funnel stage hierarchy
│   │       ├── analytics.py              # Mathematical aggregations & cross-board logic
│   │       └── quality_report.py         # Null-rate governance and caveat generators
│   └── tests/                       # 132 comprehensive unit and integration tests
│
├── frontend/                        # React 18 + Vite 5 TypeScript web application
│   ├── src/
│   │   ├── App.tsx                  # Root layout with sidebar navigation and view switcher
│   │   ├── api.ts                   # Typed API client for FastAPI backend
│   │   ├── types.ts                 # Domain models and TypeScript contracts
│   │   ├── components/              # 3D WebGL UAV scene, chat dock, command palette, nav
│   │   │   ├── ThreeDroneOperationsScene.tsx # Procedural 3D industrial quadcopter UAV WebGL scene
│   │   │   ├── DroneOperationsHeroVisual.tsx # Interactive aerospace telemetry and 3D visual container
│   │   │   ├── ChatInput.tsx        # Aerospace glass input dock with auto-resize and send button
│   │   │   ├── ChatMessage.tsx      # Markdown narrative rendering and risk alert callouts
│   │   │   ├── CommandPalette.tsx   # Instant ⌘K search and natural language shortcuts
│   │   │   └── TopNav.tsx / Sidebar.tsx # Aerospace HUD header, breadcrumbs, and board status
│   │   ├── hooks/                   # use3DTilt cursor parallax and useApiResource data hooks
│   │   └── views/                   # Landing tour, Overview, Funnel, Delivery, Quality, Chat
│   └── package.json
│
├── infra/
│   ├── Dockerfile                   # Multi-stage production container build
│   └── apprunner.yaml               # Cloud container specification
│
└── scripts/
    ├── build_deal_links.py          # Multi-feature offline Deal ↔ Work Order matcher
    ├── deal_wo_links.csv            # Ground-truth link seed mapping
    └── monday_board_setup.md        # Monday.com board setup and CSV import guide
```

---

## 📊 Monday.com Board Configuration

To replicate or connect your Monday.com workspace:

1. **Work Orders Board**:
   * Create a board named `Work Orders`.
   * Import `Work_Order_Tracker Data.xlsx` (Row 1 is empty; configure Row 2 as column headers).
   * Ensure `Amount in Rupees (Excl of GST)`, `Billed Value`, and `Amount Receivable` are mapped to **Numbers** columns.
   * Ensure `Execution Status`, `Invoice Status`, and `Sector` are mapped to **Status / Dropdown** columns.
2. **Deals Board**:
   * Create a board named `Deals`.
   * Import `Deal funnel Data.xlsx` (Ensure rows 52 and 181 are removed as repeated header rows).
   * Map `Masked Deal value` to a **Numbers** column.
   * Map `Deal Stage`, `Deal Status`, and `Closure Probability` to **Status / Dropdown** columns.
3. **Cross-Board Connect Boards Column**:
   * On the `Work Orders` board, add a **Connect Boards** column named `Linked Deal`.
   * Connect it to the `Deals` board to enable live cross-board relation queries.

For exact column IDs and schema specifications, see [`scripts/monday_board_setup.md`](scripts/monday_board_setup.md).

---

## 💻 Local Setup & Development

### Prerequisites
* **Python**: 3.11 or higher
* **Node.js**: 18 or higher (with npm)
* **Monday.com API Token**: Personal API Token from Monday.com Developer section
* **Groq API Key**: API key from [console.groq.com](https://console.groq.com)

### 1. Environment Configuration
Create a `.env` file in the project root:
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

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
Interactive API documentation: `http://localhost:8000/docs`.

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Access the application: `http://localhost:5173`.

---

## 🧪 Automated Testing & Verification

The test suite validates data normalization edge cases, MCP caching, clarification decision trees, Cross-Board governance analytics, and REST endpoints:

```bash
cd backend
python -m pytest --cov=app/data --cov-report=term --cov-fail-under=75 tests/
```

### Test Suite Results (132 Passed | 94.07% Code Coverage)
```
Name                                Stmts   Miss  Cover
-------------------------------------------------------
app\data\__init__.py                    0      0   100%
app\data\analytics.py                 389     20    95%
app\data\normalize_deals.py           163     11    93%
app\data\normalize_work_orders.py     399     20    95%
app\data\quality_report.py             95     11    88%
-------------------------------------------------------
TOTAL                                1046     62    94.07%
======================= 132 passed, 1 warning in 36s =======================
```

**Test Coverage by Subsystem:**
* `test_normalize_work_orders.py` (47 tests): 71 mixed PO unit variations, negative credit balances, Excel serial date epochs, 4 null columns.
* `test_normalize_deals.py` (12 tests): Embedded header row cleaning, 16-stage pipeline hierarchy sorting, sector aliasing.
* `test_analytics.py` (13 tests): Deterministic arithmetic, weighted pipeline, customer credit balances, **cross-board commercial risk and contract value variance**.
* `test_monday_mcp.py` (12 tests): Read-only mutation defense, cursor pagination, 5-minute thread-safe TTL cache, schema introspection.
* `test_clarification.py` (6 tests): Indian Fiscal Year vs. Calendar Year disambiguation, vague horizons, suggested chip generation.
* `test_agent_orchestrator.py` (11 tests): Groq tool loop, system prompt construction, currency sanitization.
* `test_agent_tools.py` (12 tests): Tool argument validation, dispatchers, **cross-board delivery view filtering**.
* `test_api_chat.py` (12 tests): FastAPI request lifecycle, `/health`, `/api/chat`, error handling.
* `test_deal_matching.py` (7 tests): Deterministic multi-feature cross-board resolution engine.

---

## ☁️ Deployment Architecture (AWS ECS Express Mode)

The application is deployed to production using **AWS ECS Express Mode (AWS Fargate)** in the `ap-south-1` region with **Amazon ECR**:

```
[ Git Push to Main ] ──► [ Docker Multi-Stage Build ] ──► [ Amazon ECR Registry ]
                                                                   │
                                                                   ▼
                                                     [ AWS ECS Express Mode Service ]
                                                     (Fargate Serverless Container)
                                                                   │
                                                   ┌───────────────┴───────────────┐
                                                   │                               │
                                            [ React 18 SPA ]              [ FastAPI Backend ]
                                            (Static Mount)                (Port 8000, MCP, LLM)
```

### Docker Multi-Stage Build & Run
```bash
# Build production image combining Vite frontend and FastAPI backend
docker build -t skylark-bi-agent -f infra/Dockerfile .

# Run container locally with environment variables
docker run -p 8000:8000 --env-file .env skylark-bi-agent
```

### Deploying to Amazon ECR & AWS ECS
```bash
# 1. Log in to Amazon ECR
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com

# 2. Build and tag image
docker build -t skylark-bi-agent -f infra/Dockerfile .
docker tag skylark-bi-agent:latest <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/skylark-bi:latest

# 3. Push to ECR
docker push <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/skylark-bi:latest

# 4. Deploy service via AWS ECS Express Mode (Fargate) with auto-scaling and health check (/health)
```

---

## 💡 Example Conversational Prompts to Try

In the conversational interface or via `/api/chat`:

1. **Executive Leadership Briefing**:
   > *"Give me this week's leadership update."*
2. **Cross-Board Governance & Commercial Risk**:
   > *"Are we executing any work orders on deals that haven't been won yet?"*
3. **Contract Value Leakage**:
   > *"Show me any contract value variance between sales CRM commitments and work orders."*
4. **Pipeline Analytics**:
   > *"What is our unweighted and probability-weighted pipeline for the Renewables sector?"*
5. **Receivables & Credit Accounts**:
   > *"What is our net vs. gross accounts receivable position, and do we have any customer credit balances?"*
6. **Data Quality & Governance Audit**:
   > *"Generate a data quality report and tell me which columns have severe null rates."*
