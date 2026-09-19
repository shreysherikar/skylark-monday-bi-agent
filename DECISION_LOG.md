# Decision Log: Skylark Drones Monday.com BI Agent

> **Architecture Decision Record (ADR)**  
> *Documents key architectural assumptions, data trade-offs, tech stack justifications, and executive reporting methodology.*

---

## 1. Key Assumptions & Ground Truth Join Strategy

* **Join Key Reality (The Foreign Key Disconnect)**:
  * In the raw datasets, `Serial #` (`SDPLDEAL-xxx`) is 100% populated in Work Orders, but **completely absent from the Deals board** (0 of 12 columns contain it).
  * Direct composite matching on `(Deal Name, Client Code)` yields only **1 record**, because customer numbering in Work Orders (`WOCOMPANY_xxx`) and Deals (`COMPANYxxx`) occupy distinct namespaces.
  * Deal names repeat across multiple distinct clients (e.g., multiple "Sasuke" / "Sakura" records) and are **non-unique**.
* **Pre-Import Resolution & Native Connect Boards**:
  * We engineered an offline multi-feature matching engine ([`scripts/build_deal_links.py`](scripts/build_deal_links.py)) scoring candidate pairs using exact Deal Name, sector alignment, owner codes, deal won status, and date proximity between PO dates and close dates.
  * Links were categorized into confidence tiers (`MATCHED_HIGH`, `MATCHED_FUZZY`, `UNMATCHED`) and output as [`scripts/deal_wo_links.csv`](scripts/deal_wo_links.csv) to populate a native Monday.com `Connect Boards` column (`Linked Deal`).
  * On the live boards, 15 Work Orders (8.5%) have active relations. Crucially, the agent **dynamically reports live match coverage** on every cross-board query rather than hallucinating complete linkage.
* **Cross-Board Risk & Contract Leakage Audits**:
  * **Commercial Risk on Unclosed Deals**: Found 5 work orders totaling **₹20,838,860.24 Excl GST** linked to unclosed deals (Open/On Hold/Dead), including 1 active project (`SDPLDEAL-099`, Ongoing, ₹14.39M) on an Open deal (`Goku`).
  * **Contract Value Leakage / Variance**: Found 6 linked projects with contract value leakage totaling **₹114,710,914.13**, where booked scope exceeded contracted CRM deal value.
  * **Won Deals Backlog**: 96 of 103 Won Deals lack linked Work Orders on Monday.com, representing **₹101,899,594.90** in unbooked pipeline backlog.
  * **Unlinked Execution Financial Exposure**: 161 unlinked work orders represent ₹180M+ in delivery execution lacking CRM attribution.
* **Ambiguous Column Interpretations**:
  * **Blank String `''` / `null` is NOT Zero**: In financial fields (e.g., `Billed Value`, `Collected Amount`), blanks represent unrecorded/unbilled events. Coercing them silently to zero distorts averages and pipeline sums; they are preserved as `None` with mandatory caveats.
  * **Legitimate Negative Balances Preserved**:
    1. `Amount Receivable`: 11 negative rows (min −₹160.24) represent **customer credit balances and overpayments**. Clamping to zero would falsely inflate accounts receivable. Both **Gross Receivables** (₹3,62,91,913.69) and **Net Receivables** (₹3,62,91,748.87) are reported.
    2. `Amount to be billed`: 6 negative rows (totaling −₹1,08,311.72 Excl GST) reflect scope and volume adjustments.
    3. `Balance in quantity`: 2 negative rows (−0.01 and −1,309.85) reflect execution exceeding estimated quantities.
  * **Four 100% Null Columns**: `Expected Billing Month`, `Actual Collection Month`, `Collection status`, and `Collection Date` contain 0 populated rows across all 176 items. They are preserved in typed schemas and surfaced in governance telemetry.
  * **Orthogonal Status Dimensions**: `Execution Status` (fulfillment), `Invoice Status` (billing), `WO Status (billed)` (ERP account closure), and `Billing Status` (exception handling) are modeled as four separate typed enums to prevent conflation.

---

## 2. Tech Stack Selection & Justification

| Layer | Choice | Architectural Justification |
| :--- | :--- | :--- |
| **Reasoning Engine** | **Groq SDK** (`openai/gpt-oss-120b` / `llama-3.3-70b-versatile`) | Provides ultra-low latency tool calling (~500ms) with open-weights model flexibility. Strictly constrained to intent parsing, tool dispatch, and narrative synthesis—zero arithmetic executed in the model. |
| **MCP Server** | **Python `mcp` SDK** | Implements the open Model Context Protocol standard over Monday.com GraphQL API v2. Provides structured introspection, schema-aware retrieval, and code-level mutation defense shields. |
| **Backend Framework**| **FastAPI (Python 3.11+)** | High-performance asynchronous REST framework with native OpenAPI schema validation, Pydantic v2 typing, and seamless single-container static file serving. |
| **Data Normalization**| **Pandas & Pydantic v2** | Explicit, testable data transformation pipelines. Handles regex parsing across 71 free-text PO quantity units (`5360 HA`, `40MW`, `415Acers`) and Excel serial date conversions. |
| **Frontend UI** | **React 18 + Vite 5 (TypeScript)** | Executive dark-mode glassmorphic dashboard with instant keyboard navigation (`⌘K` Command Palette), real-time telemetry cards, cross-board alignment matrix, and dynamic API binding. |
| **Deployment** | **AWS ECS Express Mode (AWS Fargate)** | Serverless container deployment in AWS `ap-south-1` via Amazon ECR, providing rapid zero-setup evaluator access. |
| **Testing** | **Pytest & Pytest-Cov** | 132 comprehensive unit and integration tests (94.07% coverage) enforcing strict coverage on normalization, arithmetic precision, and edge cases. |

---

## 3. Trade-offs Chosen & Scope Calibration

* **Deterministic Python Analytics vs. In-Prompt Arithmetic**:
  * *Trade-off*: Writing 10+ deterministic Python analytics functions and 132 unit tests required significantly more engineering effort than asking Claude/Groq to "analyze this table."
  * *Why*: LLMs frequently hallucinate calculations over real-world data with missing values. The architectural separation guarantees that every number in the executive briefing matches Monday.com ground truth.
* **Single-Container Deployment vs. Microservices Sprawl**:
  * *Trade-off*: Bundling the compiled React SPA inside the FastAPI container rather than provisioning separate AWS Amplify and ECS clusters.
  * *Why*: Senior engineering prioritizes zero-configuration operational reliability, reproducible deployments, and sub-second container cold starts over unneeded infrastructure sprawl.
* **In-Memory TTL Caching vs. External Database**:
  * *Trade-off*: Monday.com is maintained as the single source of truth using an in-memory 5-minute thread-safe TTL cache rather than provisioning an external PostgreSQL/RDS sync pipeline.
  * *Why*: Keeps Monday.com as the live single source of truth without data stale-out while preventing API rate limiting on high-frequency queries.

---

## 4. Interpretation of "Leadership Updates"

Designed as an **automated, C-suite executive briefing generator**:
1. **Core Financial & Pipeline KPIs**: Summarizes unweighted active pipeline, probability-weighted pipeline, closed-won revenue, total work order bookings, billed revenue, collections, and net vs. gross receivables.
2. **Delivery & Fulfillment Velocity**: Reports work order execution status breakdowns and invoice status breakdowns.
3. **Cross-Board Operational Alignment**: Displays matched vs. unlinked order metrics and fulfilled won projects.
4. **Active Governance & Bookkeeping Risks**: Automatically attaches high-visibility alerts (commercial risk on unclosed deals, contract value variance, customer credit accounts, missing deal values, and unassigned closure probabilities).
5. **Format & Workflow**: Generates clean, executive Markdown ready to be copied into Slack, executive memos, or investor reports at the touch of a button.

---

## 5. What We Would Do Differently With More Time

1. **Webhook-Driven Real-Time Sync**: Replace the 5-minute TTL polling cache with incoming Monday.com webhooks for instant board change invalidation.
2. **Automated Link Resolution Assistant**: Build an interactive disambiguation workflow allowing business owners to review and confirm fuzzy deal-order matches.
3. **Multi-Turn Chart Visualization**: Add native export capabilities generating vector PDF slide decks directly from conversational prompts.

---

## 6. Known Limitations

1. **Live Board Linkage Coverage**: Exactly 15 of 176 Work Orders (8.5%) currently have populated `Connect Boards` links on Monday.com. The agent explicitly caveats that cross-board delivery metrics represent matched records only.
2. **Deals Data Gaps in Source Board**: `Close Date (A)` is 92.4% null (only 26 dates recorded out of 344), `Closure Probability` is 75.0% null, and `Masked Deal value` is 52.0% null. All pipeline summaries explicitly report these completeness percentages.
3. **Qualitative PO Quantities**: A small subset of legacy orders contain unstructured text like `"L/s"` (lump sum) or `"Rate based on MW slabs"` where numeric volume extraction is mathematically impossible.
