# Decision Log: Skylark Drones Monday.com BI Agent

> **Architecture Decision Record (ADR)**  
> *Documents key architectural assumptions, data trade-offs, tech stack justifications, structured response contracts, adversarial QA findings, and executive reporting methodology.*

---

## 1. Key Assumptions & Ground Truth Join Strategy

* **Join Key Reality (The Foreign Key Disconnect)**:
  * In the raw datasets, `Serial #` (`SDPLDEAL-xxx`) is 100% populated in Work Orders, but **completely absent from the Deals board** (0 of 12 columns contain it).
  * Direct composite matching on `(Deal Name, Client Code)` yields only **1 record**, because customer numbering in Work Orders (`WOCOMPANY_xxx`) and Deals (`COMPANYxxx`) occupy distinct namespaces.
  * Deal names repeat across multiple distinct clients (e.g., multiple "Sasuke" / "Sakura" records) and are **non-unique**.
* **Pre-Import Resolution vs. Live Native Connect Boards**:
  * An offline multi-feature matching engine ([`scripts/build_deal_links.py`](scripts/build_deal_links.py)) was developed to score candidate pairs using exact Deal Name, sector alignment, owner codes, deal won status, and date proximity between PO dates and close dates.
  * High-confidence links were exported to [`scripts/deal_wo_links.csv`](scripts/deal_wo_links.csv) to initially populate a native Monday.com `Connect Boards` column (`Linked Deal`).
  * **Live Board Mechanism**: The live production runtime relies **exclusively** on Monday's native Connect Boards column when querying live data via MCP. It does **not** fall back to offline CSV candidate files during live execution.
  * **Ground Truth Linkage Statistics**: Exactly **15 of 176 Work Orders (8.5%)** have confirmed native Connect Board relations on the live Monday.com board.
  * **Strict Linkage Boundary**: Cross-board analytics only treats confirmed native Monday Connect Board relationships as confirmed links. Unmatched records (161 work orders) are strictly categorized as unlinked and are **never silently inferred or assumed as linked**.
* **Cross-Board Risk & Contract Leakage Audits**:
  * **Commercial Risk on Unclosed Deals**: Found 5 work orders totaling **₹20,838,860.24 Excl GST** linked to unclosed deals (Open/On Hold/Dead), including 1 active project (`SDPLDEAL-099`, Ongoing, ₹14.39M) executing against an Open deal (`Goku`).
  * **Contract Value Leakage / Variance**: Found 6 linked projects with contract value leakage totaling **₹114,710,914.13**, where booked scope exceeded contracted CRM deal value.
  * **Won Deals Backlog**: 96 of 103 Won Deals lack linked Work Orders on Monday.com, representing **₹101,899,594.90** in unbooked pipeline backlog.
  * **Unlinked Execution Financial Exposure**: 161 unlinked work orders represent **₹180M+** in delivery execution lacking CRM attribution.
* **Ambiguous Column Interpretations**:
  * **Blank String `''` / `null` is NOT Zero**: In financial fields (e.g., `Billed Value`, `Collected Amount`), blanks represent unrecorded/unbilled events. Coercing them silently to zero distorts averages and pipeline sums; they are preserved as `None` with mandatory caveats.
  * **Legitimate Negative Balances Preserved**:
    1. `Amount Receivable`: 11 negative rows (min −₹160.24) represent **customer credit balances and overpayments**. Clamping to zero would falsely inflate accounts receivable. Both **Gross Receivables** (₹3,62,91,913.69) and **Net Receivables** (₹3,62,91,748.87) are reported.
    2. `Amount to be billed`: 6 negative rows (totaling −₹1,08,311.72 Excl GST) reflect scope and volume adjustments.
    3. `Balance in quantity`: 2 negative rows (−0.01 and −1,309.85) reflect execution exceeding estimated quantities.
  * **Four 100% Null Columns**: `Expected Billing Month`, `Actual Collection Month`, `Collection status`, and `Collection Date` contain 0 populated rows across all 176 items. They are preserved in typed schemas and surfaced in governance telemetry.
  * **Embedded Header Contamination Suppressed**: Deals board records 52 and 181 contain embedded table headers from manual copy-paste operations; these are filtered out dynamically during normalization to yield exactly 344 valid deals.
  * **Orthogonal Status Dimensions**: `Execution Status` (fulfillment), `Invoice Status` (billing), `WO Status (billed)` (ERP account closure), and `Billing Status` (exception handling) are modeled as four separate typed enums to prevent conflation.

---

## 2. Tech Stack Selection & MCP Architecture Decision

### Tech Stack Rationale

| Layer | Choice | Architectural Justification |
| :--- | :--- | :--- |
| **Reasoning Engine** | **Groq SDK** (`llama-3.3-70b-versatile`) | Provides low-latency tool calling (~500ms) with open-weights model flexibility. Strictly constrained to intent parsing, tool dispatch, and narrative synthesis—business arithmetic is performed by deterministic Python analytics. |
| **MCP Integration** | **Python `mcp` SDK + Monday GraphQL v2** | Implements standard Model Context Protocol server exposing read-only data access with cursor pagination, dynamic schema introspection, and pre-dispatch mutation defense. |
| **Backend Framework**| **FastAPI (Python 3.11+)** | High-performance asynchronous REST framework with native OpenAPI schema validation, Pydantic v2 typing, and single-container static file serving. |
| **Data Normalization**| **Pandas & Pydantic v2** | Explicit, testable data transformation pipelines. Handles regex parsing across free-text PO quantity units (`5360 HA`, `40MW`, `415Acers`), currency cleaning, and Excel serial date conversions. |
| **Frontend UI** | **React 18 + Vite 5 (TypeScript)** | Dark-mode executive glassmorphic dashboard with instant keyboard navigation (`⌘K` Command Palette), structured KPI cards, risk callout banners, and evidence drawer. |
| **3D Visual Engine** | **Three.js (WebGL)** | Procedural 3D industrial quadcopter UAV with organic hover bobbing, mouse parallax tilt, rotating carbon propellers, and illuminated Earth operations globe running at 60 FPS. |
| **Deployment** | **AWS ECS Express Mode (AWS Fargate)** | Serverless container deployment in AWS `ap-south-1` via Amazon ECR, providing rapid zero-setup evaluator access. |
| **Testing** | **Pytest & Pytest-Cov** | Comprehensive unit, integration, and live verification suites (154 normal tests + 5 live tests) enforcing strict coverage on normalization, arithmetic precision, and edge cases. |

### MCP Architecture Decision

* **Why MCP Was Adopted**:
  * Standardizes data retrieval behind a protocol-level boundary, separating external data extraction from internal analytics computation.
  * Provides native protocol-level discoverability, structured schema introspection, and resource URI semantics.
  * Shields backend analytics from changes in Monday.com API transport details.
* **Minimal Public Tool Surface**:
  * Exactly **3 public MCP tools** are registered on the MCP server:
    1. `get_work_orders`: Fetches and normalizes all 176 work orders with column values, connect-board relations, and status enums.
    2. `get_deals`: Fetches and normalizes 344 CRM deals with financial values, stages, closure probabilities, and sectors.
    3. `get_schema`: Dynamic schema introspection returning column IDs, titles, and types for any board.
  * `get_board_schema`: Maintained as a Python backward-compatibility alias in `MondayMCPClient`, but **not** registered as an independent MCP tool to avoid surface duplication.
* **Security & Reliability Controls**:
  * **Mutation Shield**: Pre-dispatch inspection inspects all GraphQL operations before network transmission. Any query containing `mutation`, `create_`, `update_`, `delete_`, or `change_` is blocked immediately with a permission violation.
  * **Cursor Pagination**: Transparently handles Monday.com API v2 500-item page limits via GraphQL `cursor` pagination until exhaustion.
  * **Thread-Safe In-Memory TTL Cache**: 5-minute TTL cache minimizes redundant Monday.com API calls and protects against upstream rate limits.
  * **Read-Only MCP Resources**: Exposes `monday://work_orders`, `monday://deals`, and `monday://schema/{board_type}` for protocol-compliant resource consumers.

---

## 3. Trade-offs Chosen & Scope Calibration

* **Deterministic Python Analytics vs. In-Prompt Arithmetic**:
  * *Trade-off*: Writing dedicated deterministic Python analytics modules and 150+ unit/integration tests required significantly more engineering rigor than simply prompting an LLM to "calculate total revenue from this JSON."
  * *Why*: Large Language Models cannot be trusted to perform exact arithmetic over multi-thousand-cell datasets with missing values, currency strings, disparate units, and negative credit balances.
  * *The Architectural Boundary*:
    > **"The LLM is responsible for intent interpretation, tool orchestration, and narrative synthesis. Business arithmetic is performed by deterministic Python analytics."**
    Every KPI, variance calculation, status breakdown, and risk metric is computed in Python using IEEE floating-point / Decimal precision before the LLM ever sees it.
* **Structured Response Contracts vs. Plain-Text Freeform Generation**:
  * *Trade-off*: Creating formal Pydantic response models (`StructuredCopilotResponse`) and building specialized frontend rendering components for KPI cards, risk callouts, and evidence provenance drawers.
  * *Why*: C-suite executives require glanceable metrics, explicit confidence boundaries, and source data transparency. Freeform markdown responses hide calculation methodologies and are prone to subtle omissions.
* **Deterministic Tool Payload Compaction for LLM Context**:
  * *Trade-off*: Compacting large multi-record lists into summary statistics and representative previews in tool return payloads, while preserving complete data in structured response models.
  * *Why*: Groq's on-demand API enforces an 8,000 Tokens Per Minute (TPM) limit. Uncompressed dumps of 176 work orders or 344 deals trigger HTTP 429 / 413 errors. Compaction keeps prompt context well under 1,500 tokens without sacrificing analytical accuracy.
* **In-Memory TTL Caching vs. External Database Infrastructure**:
  * *Trade-off*: Maintaining Monday.com as the live single source of truth backed by an in-memory 5-minute thread-safe TTL cache rather than provisioning an external PostgreSQL/RDS sync pipeline.
  * *Why*: Eliminates stale data drift and unnecessary infrastructure overhead while shielding Monday.com APIs from excessive request bursts.
* **Verified Test Coverage vs. Live Dependency in CI**:
  * *Trade-off*: Separating deterministic unit/integration tests (using robust mock fixtures) from live Monday.com tests.
  * *Why*: CI/CD pipelines must remain fast, deterministic, and runnable without external API tokens or network dependencies. Live verification is encapsulated in `tests/test_monday_live.py` (explicitly marked with `@pytest.mark.live` and deselected by default).
  * *Current Verified Test Baseline*:
    * **155 passed**, 5 deselected in normal test suite.
    * **5 passed** in live test suite against live Monday.com boards.
    * **0 Ruff errors**, **0 mypy type errors**.
    * Vite React frontend build clean (exit code 0).

---

## 4. Interpretation of "Leadership Updates"

The system is calibrated as an **automated, C-suite executive briefing generator**:

1. **Core Financial & Pipeline KPIs**: Reports unweighted active pipeline, probability-weighted pipeline, closed-won revenue, total work order bookings, billed revenue, collections, and net vs. gross receivables.
2. **Delivery & Fulfillment Velocity**: Reports work order execution status breakdowns and invoice status breakdowns.
3. **Cross-Board Operational Alignment**: Displays matched vs. unlinked order metrics and fulfilled won projects.
4. **Active Governance & Commercial Risks**: Automatically attaches high-visibility alerts:
   - Commercial execution risk on unclosed deals.
   - Contract value leakage (booked scope exceeding deal value).
   - Customer credit accounts (negative receivables).
   - Data gaps (missing deal values, unassigned closure probabilities).
5. **Format & Delivery**: Produces dual-layer output: structured UI components for interactive dashboard review and clean executive Markdown ready for Slack, email memos, or investor updates.

---

## 5. Structured Response Architecture Decision

### Context
Initially, the copilot returned markdown narrative responses that required the React frontend to parse unstructured text. While visually acceptable, it prevented reliable visual distinction between executive summaries, high-priority risks, verified KPIs, and evidence provenance.

### Decision
Introduce [`StructuredCopilotResponse`](backend/app/agent/structured_response.py) as a strongly-typed Pydantic contract between the agent orchestration layer and the React frontend.

```json
{
  "summary": "...",
  "kpis": [
    { "label": "...", "value": "...", "context": "..." }
  ],
  "risks": [
    { "title": "...", "detail": "...", "severity": "high|medium|low" }
  ],
  "evidence": {
    "sources": ["Work Orders", "Deals"],
    "records_analyzed": 176,
    "data_coverage": "...",
    "calculation": "..."
  },
  "data_quality_caveats": ["..."],
  "recommended_follow_ups": ["..."]
}
```

### Rationale
1. **Executive Presentation**: The UI renders dedicated KPI cards, color-coded risk callouts, evidence drawers, and clickable follow-up chips while preserving markdown narrative rendering for general discussion.
2. **Provenance & Traceability**: Clearly separates analytical metadata (sources used, record counts analyzed, match coverage percentages, calculation methodology notes) from conversational text.
3. **Deterministic Origin**: Every KPI value, risk count, and evidence record in the structured payload is extracted directly from deterministic tool outputs (`DataQualityReport`, `CrossBoardReconciliationReport`, `FinancialSummaryReport`, `RiskReport`). The LLM does not generate structured metrics from scratch.
4. **Cognitive Hygiene**: LLM internal chain-of-thought (`<think>...</think>`) tags are stripped prior to delivery, ensuring leadership never sees raw scratchpad reasoning.
5. **Backward Compatibility**: If a prompt does not require structured formatting (e.g., greetings, general help), the agent transparently falls back to clean plain-text responses without breaking the frontend.

---

## 6. Final Adversarial QA Findings & Hardening

During the final adversarial QA audit, the codebase was stress-tested against boundary conditions, mock degradation, rate limits, and fallback paths. Four key findings were identified and addressed:

### 1. Join Work Orders Fallback Hardening
* **Defect**: In [`backend/app/data/analytics.py`](backend/app/data/analytics.py), `join_work_orders_to_deals` contained a fallback to read `scripts/deal_wo_links.csv` when `linked_pairs` was empty. When querying live Monday.com data with 0 linked items (or in scenarios where relation data was absent), this could silently pull candidate links from the static CSV file.
* **Fix**: Hardened the resolution logic so that when `wo_items` is provided (indicating a live Monday.com query), the function strictly respects the live Monday.com Connect Board relationships (even if 0) and **never** falls back to the offline CSV file. The CSV fallback is restricted strictly to offline test runs where no live work order items are provided.

### 2. Structured Response Metric Hardcoding Elimination
* **Defect**: In [`backend/app/agent/tools.py`](backend/app/agent/tools.py), `build_quality_structured` contained hardcoded fallback values for record counts (`176`, `344`), null column counts (`4`), and customer credit balance accounts (`11`).
* **Fix**: Replaced all hardcoded integers and static strings with dynamic extractions from the deterministic `DataQualityReport` object. If board records change, structured responses immediately reflect live data counts.

### 3. Groq API Rate Limiting Resilience
* **Finding**: Groq's on-demand free tier enforces an 8,000 TPM limit. Rapid multi-turn queries or complex prompts could trigger transient HTTP 429 (`RateLimitError`) exceptions.
* **Fix**: Implemented an exponential backoff retry loop in `AgentOrchestrator._create_completion` (up to 3 retries with `3.0s * (attempt + 1)` backoff) that catches `RateLimitError` and recovers transparently before failing over.

### 4. Response Truncation Assessment
* **Finding**: The orchestrator's `max_tokens=2048` parameter was evaluated to determine if verbose leadership responses could suffer mid-sentence truncation.
* **Assessment**: Validated as an intentional and appropriate design constraint. It enforces executive-grade conciseness, prioritizes structured KPI cards, and prevents runaway token consumption. Tool payloads are already pre-compacted to prevent context overflow.

### 5. Copilot Presentation & Formatting Hardening
* **Data Quality Null Rate Formatting**: Eliminated a presentation bug where core null rates (which are already percentages, e.g. 92.4, 75.0) were multiplied by 100 in risk callouts, displaying erroneous 9244% and 7500% figures. Values now cleanly render as 92.4% and 75.0%.
* **100% Null Columns Enumeration**: Fixed risk detail generation to list all four empty columns (`Expected Billing Month`, `Actual Collection Month`, `Collection status`, `Collection Date`) rather than truncating the display to three.
* **Receivables Phrasing Precision**: Replaced misleading "as of today" wording with "Current Outstanding Receivables Across Current Work Orders" to prevent implying historical date-cutoff accounting logic that does not exist in the source dataset.
* **Non-Won vs. Unclosed Deal Clarity**: Hardened cross-board risk wording to state that "5 confirmed linked work orders are ongoing or completed against deals that are not in a Won state" (recognizing that some orders are Completed, and deal stages include Open, On Hold, or Dead).
* **Unlinked Booked Value Attribution**: Calibrated unlinked revenue wording to state that "₹184.07M of booked work-order value is currently unlinked to a confirmed CRM deal on Monday.com", avoiding the overstatement that the underlying customer contracts themselves are unknown.
* **Grounded Management Recommendations**: Stripped speculative quantitative targets (e.g. "≥50% coverage in 30 days") and rigid policy mandates, reframing suggestions as exploratory review actions ("Potential action: Review and increase native Deal ↔ Work Order linkage coverage").

---

## 7. What We Would Do Differently With More Time

1. **Webhook-Driven Real-Time Invalidation**: Replace the 5-minute TTL polling cache with incoming Monday.com webhooks (`change_column_value`, `item_created`) for event-driven cache eviction.
2. **Interactive Link Resolution Assistant**: Build a human-in-the-loop copilot action allowing account executives to approve or reject fuzzy deal-order link candidates directly within the chat interface.
3. **Native Slide Deck / PDF Export**: Add server-side headless Chromium rendering to export conversation briefings and visual telemetry directly to formatted PDF executive memos.

---

## 8. Known Limitations

1. **Live Board Linkage Coverage**: Exactly 15 of 176 Work Orders (8.5%) currently have populated `Connect Boards` links on Monday.com. The agent explicitly caveats that cross-board delivery metrics represent matched records only.
2. **Deals Data Gaps in Source Board**: `Close Date (A)` is 92.4% null (only 26 dates recorded out of 344), `Closure Probability` is 75.0% null, and `Masked Deal value` is 52.0% null. All pipeline summaries explicitly report these completeness percentages.
3. **Qualitative PO Quantities**: A small subset of legacy orders contain unstructured text like `"L/s"` (lump sum) or `"Rate based on MW slabs"` where numeric volume extraction is mathematically impossible.
4. **Groq API Rate Limits**: The on-demand tier's 8,000 TPM quota requires compact tool payloads and retry backoffs; enterprise production would deploy dedicated inference endpoints or higher-tier rate limits.
