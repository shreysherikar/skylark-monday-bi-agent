# Architectural Decision Log & Assumptions

> **Engineering Appendix**: For structured response JSON schemas, data cleaning regexes, and adversarial QA records (ADRs 1–10), see [`docs/ARCHITECTURE_NOTES.md`](docs/ARCHITECTURE_NOTES.md).

---

## 1. Key Assumptions

1. **Temporal Horizon & Dataset Boundary**: The source dataset spans historically through early 2026 (latest recorded deal: April 2026). When evaluated against current dates (e.g., Sept 20, 2026 = Q2 FY26-27), the active quarter contains zero deals. Rather than printing misleading zeros, the agent assumes an empty-period state, explains the historical dataset boundary, and surfaces the nearest historical quarters with data (`FY25-26 Q4`, `Q3`, `Q2`).
2. **Deals Stage Hierarchy & Won Definition**: `is_won` is determined by sales funnel progression (`Deal Stage` in Stages G through K + Project Completed), identifying **103 Won deals** (total contract value ₹108.58M across 344 genuine deal records). The subset of Won deals with populated `Close Date (A)` or `Tentative Close Date` is 94. Won deal value represents signed contract value, not earned revenue.
3. **Bookings vs. Earned Revenue**: Work Orders time-slicing anchors on `Date of PO/LOI` (175 non-null records) and strictly represents **Bookings (by PO date)**. Billed and collected amounts cannot be time-sliced by quarter because billing and collection dates (`Expected Billing Month`, `Actual Collection Month`, `Collection Date`) are 100% unpopulated in Monday.com.
4. **DSO & Aging Refusal**: Days Sales Outstanding (DSO) and invoice aging are mathematically uncomputable from source data because collection dates and billing months are 100% null. The agent explicitly refuses to fabricate aging or DSO estimates.
5. **Owner Ranking Namespace Separation**: Deals `Owner code` tracks CRM sales negotiation, while Work Orders `BD/KAM Personnel code` tracks post-sales operations and fulfillment. Because masked identifiers share the `OWNER_XXX` format but lack cross-board personnel mapping, they are assumed to represent distinct functional roles and are ranked independently (Deals Sales Owners by Won Value; Operations Personnel by Bookings).
6. **Board Linkage & External Setup**: A one-time administrative script was used prior to agent execution to establish native Monday `Connect Boards` links on the sample board using `deal_wo_links.csv`. At runtime, the agent is strictly read-only, executes zero mutations, never writes to Monday.com, and dynamically inspects live board links (discovering 15 of 176 linked orders, 8.5% coverage) with zero offline CSV fallbacks.

---

## 2. Trade-Offs & Tech Stack Justification

| Technology / Pattern | Decision & Implementation | Architectural Trade-Off & Rationale |
| :--- | :--- | :--- |
| **LLM Reasoning** | Groq SDK (`openai/gpt-oss-120b`) | High-throughput tool calling with deterministic compact tool payloads and exponential backoff retry for rate-limit resilience. Free-tier token caps (8k TPM) require strict output payload compaction in `orchestrator.py`. |
| **MCP Integration** | In-process invocation of Python MCP tools | The MCP server is fully implemented and tested under official MCP SDK contracts (`get_work_orders`, `get_deals`, `get_schema`). Runtime calls its functions in-process to avoid subprocess spawn latency (~300ms) and operational complexity while preserving schema isolation. |
| **Deterministic Analytics** | Pure Python calculation via Pandas & `date_resolver.py` | 100% of financial aggregations, GST validations, win rates, and date boundary math are executed deterministically in Python. The LLM is strictly prohibited from performing arithmetic or calendar calculations. |
| **Date Resolution** | Deterministic Indian Fiscal Year in IST (`UTC+05:30`) | Relative queries ("this quarter", "last quarter") default deterministically to the Indian FY (April 1 to March 31). Clarification modals for "this quarter" were eliminated to maintain seamless conversational flow. |
| **Security & Rate Limiting** | Regex pre-transmission shields + FastAPI sliding window | Mutation operations are blocked via regex before network dispatch. The `/api/chat` endpoint enforces an in-memory sliding-window rate limiter (60 req/min per IP) returning HTTP 429 on bursts. |
| **Verification Baseline** | 169 passed tests across 15 suites; Ruff & Pydantic v2 | Guarantees regression protection across all parsing, temporal math, tool dispatching, and API routes. Strict typing enforced via Pydantic v2 runtime models and Ruff linting. |

---

## 3. What We Would Do Differently With More Time

1. **Golden-Question Evaluation Suite in CI**: Implement an automated evaluation harness running 50+ benchmark business questions against live/mock boards on every pull request, measuring factual accuracy, citation correctness, and hallucination rate against ground truth.
2. **Authentication & Multi-Tenant Authorization**: Place an enterprise authentication proxy (OAuth2 / OIDC JWT bearer tokens) in front of the FastAPI REST API, enforcing role-based access control (RBAC) so junior sales reps cannot view sensitive executive financial margins.
3. **Multi-Provider LLM Fallback & Streaming**: Implement automatic multi-model failover (Groq -> Anthropic Claude 3.5 Sonnet -> OpenAI GPT-4o) with Server-Sent Events (SSE) streaming, ensuring zero downtime if a single inference provider experiences regional rate limits or outages.
4. **End-to-End Observability & Tracing**: Integrate OpenTelemetry with structured correlation request IDs, token consumption metrics, tool execution latency distributions, and upstream Monday.com GraphQL complexity tracking.

---

## 4. How We Interpreted "Leadership Updates"

Leadership updates are designed for founders and executives who require immediate visibility into commercial velocity, operational fulfillment risks, and cash flow integrity:

1. **Temporal Parameterization**: The leadership update accepts an optional `period` parameter (e.g. "this quarter", "Q4 FY25-26", or all-time). If the queried period falls outside the dataset window, it surfaces a prominent timeline notice and benchmarks nearest historical quarters.
2. **Executive Financial & Pipeline KPIs**: Summarizes unweighted and probability-weighted active pipeline, Won deal contract value (clarified as signed contract value, not earned revenue), Win Rate calibrated as `Won / (Won + Dead)` (excluding open deals from the denominator), Bookings (by PO date), and net/gross accounts receivable.
3. **Cross-Board Governance & Commercial Risk**: Highlights unclosed deal risk—identifying work orders actively executing or completed against deals that are not yet marked Won (including high-value project `SDPLDEAL-099` totaling ₹14.39M linked to an Open proposal)—and reports live native Connect Boards link coverage (15 of 176, 8.5%).
4. **Independent Commercial Leadership Rankings**: Renders independent top-performer rankings for CRM Sales Owners (by Won contract value) and Operations Personnel (by Bookings), preventing misleading conflation of pre-sales and post-sales personnel codes.
5. **Actionable Review Items**: Replaces arbitrary AI mandates with objective, data-driven review recommendations (e.g., reviewing mandatory status on Close Date and expanding native Deal ↔ Work Order board links).
