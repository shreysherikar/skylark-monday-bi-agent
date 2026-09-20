# Architecture Notes & Engineering Appendix

This document serves as the technical companion to [`DECISION_LOG.md`](../DECISION_LOG.md), detailing the underlying data models, runtime schemas, ADR history, and adversarial hardening traces.

---

## 1. Structured Copilot Response Schema

All analytical responses emitted by the agent attach a structured, leadership-ready payload defined by `StructuredCopilotResponse` in [`backend/app/agent/structured_response.py`](../backend/app/agent/structured_response.py):

```json
{
  "summary": "High-level deterministic narrative answering the user's prompt",
  "kpis": [
    {
      "label": "Won Deal Value",
      "value": "₹108,581,976.98",
      "context": "Across 103 closed-won deals"
    },
    {
      "label": "Win Rate",
      "value": "51.0%",
      "context": "103 won / 202 decided deals (Open/On Hold excluded)"
    },
    {
      "label": "Bookings (by PO date)",
      "value": "₹184,074,383.00",
      "context": "175 work orders with recorded PO dates"
    }
  ],
  "risks": [
    {
      "title": "Commercial Risk in Unclosed Deals",
      "detail": "Work orders are actively executing against proposals not marked Won (including project SDPLDEAL-099 totaling ₹14.39M linked to an Open proposal).",
      "severity": "high"
    }
  ],
  "evidence": {
    "sources": ["Monday.com Deals Board", "Monday.com Work Orders Board"],
    "records_analyzed": 520,
    "data_coverage": "15 of 176 Work Orders linked natively (8.5% coverage)",
    "calculation": "Deterministic Python aggregation via pandas and date_resolver"
  },
  "caveats": [
    "Collection Date and Expected Billing Month are 100% null; DSO and invoice aging cannot be computed.",
    "Deal value is unrecorded for 179 of 344 deals (52.0%)."
  ],
  "follow_ups": [
    "Show me contract value leakage between Deals and Work Orders",
    "List the 8 unclosed work orders with active execution"
  ]
}
```

*Note: Keys strictly use `caveats` and `follow_ups` to match the Pydantic model contract in `structured_response.py`.*

---

## 2. Connect Boards Linkage Mechanics & CSV Setup

* **Manual Setup (One-Time Outside Agent)**: Prior to deploying the agent, a one-time administrative script was used to establish native Monday `Connect Boards` relations on the sample board using `scripts/deal_wo_links.csv`. This setup was performed entirely external to the agent.
* **Agent Read-Only Boundary**: At runtime, the agent possesses **zero write permissions** and never modifies Monday.com boards or executes GraphQL mutations.
* **Live Discovery**: The agent dynamically parses incoming `Connect Boards` column values from the Monday GraphQL v2 API, discovering exactly 15 valid linked pairs (8.5% coverage) on the live board. The agent never falls back to local CSV files for query answers.

---

## 3. Adversarial QA Findings & Architectural Decision Records (ADRs)

During adversarial QA audits, the codebase was hardened against boundary failures, missing data horizons, and edge cases:

### ADR 1: Complete Removal of Offline CSV Link Fallback
* Runtime cross-board joins strictly inspect live Monday.com `Connect Boards` relations (`15 of 176` orders, 8.5% coverage). Unmatched records are transparently reported as unlinked, guaranteeing zero heuristic guessing at runtime.

### ADR 2: Temporal Filtering & Date Anchor Methodology
* **Deals Anchoring**: Won and Dead deals anchor on `Close Date (A)` with automatic fallback to `Tentative Close Date` (103 won deals, 99 dead deals). Open and On Hold deals anchor strictly on `Tentative Close Date` (142 deals).
* **Work Orders Anchoring**: Sliced by `Date of PO/LOI` (175 non-null rows). PO date slicing represents **Bookings**, NOT revenue. All metrics and cards are labeled **"Bookings (by PO date)"**.
* **Deterministic Resolution**: Indian Fiscal Year (April 1 to March 31) in IST (`UTC+05:30`) is computed deterministically in Python via [`date_resolver.py`](../backend/app/data/date_resolver.py). The LLM is prohibited from calculating dates.

### ADR 3: Empty Quarter Boundary Handling & Historical Benchmarks
* The provided dataset records end in early 2026. Querying "this quarter" on Sept 20, 2026 yields Q2 FY26-27 (0 deals, 0 orders). The agent explicitly explains the historical boundary and presents the nearest historical quarters with data (`FY25-26 Q4`, `Q3`, `Q2`) alongside all-time metrics.

### ADR 4: DSO & Aging Refusal Policy
* `Expected Billing Month`, `Actual Collection Month`, `Collection status`, and `Collection Date` are 100% unpopulated (null) in Monday.com. The agent explicitly refuses to fabricate DSO or aging metrics.

### ADR 5: Energy Sector Aggregation
* "Energy" is modeled as an aggregate of `Renewables + Powerline` across query understanding (`clarification.py`) and analytics (`analytics.py`), returning combined metrics plus individual component breakdowns.

### ADR 6: Win Rate Calibration
* Calibrated strictly as `Won / (Won + Dead) * 100%`, explicitly excluding Open and On Hold deals from the denominator, and reporting the sample size of decided deals.

### ADR 7: System Prompt Hardcoding Clean-Up
* Stripped all static numbers from `SYSTEM_PROMPT`. The agent dynamically quotes numbers returned by live tool calls.

### ADR 8: In-Process MCP Tool Invocation
* MCP server is implemented and tested under official MCP SDK contracts; runtime calls its functions in-process to avoid subprocess spawn latency (~300ms) and operational complexity.

### ADR 9: Owner Rankings & Namespace Separation
* Deals `Owner code` (CRM sales negotiation) and Work Orders `BD/KAM Personnel code` (Operations execution) are tracked and ranked independently to reflect distinct functional roles and unconfirmed cross-board identity.

### ADR 10: Secrets Audit & Safe Submission Packaging
* Verified via full commit history traversal (`git log -S`) that live API keys were never committed. Official packaging mandates `git archive -o skylark-submission.zip HEAD` to strictly export git-tracked files.

---

## 4. Test Suite Baseline (169 Passed Tests)

All 169 offline unit and integration tests pass across 15 test suites:
- `test_agent_orchestrator.py` (7 tests): Tool execution loop, rate-limit backoff, and system prompt formatting.
- `test_agent_tools.py` (5 tests): Schemas, period arguments, and dispatching.
- `test_analytics.py` (18 tests): Deterministic revenue, pipeline, delivery, win rate, and owner breakdowns.
- `test_api_chat.py` (13 tests): FastAPI REST endpoints, error states, and sliding-window rate limiting.
- `test_clarification.py` (6 tests): Relative timeframes, sector aliasing, and dynamic FY chips.
- `test_date_resolver.py` (8 tests): Indian FY calendar boundaries, relative quarters, and fallback parsing.
- `test_deal_matching.py` (4 tests): Connect Boards parsing and link coverage calculation.
- `test_monday_mcp.py` (12 tests): Read-only MCP tools, schema inspection, and mutation blocking.
- `test_normalize_deals.py` (10 tests): Header filtering, stage classification, and null preservation.
- `test_normalize_work_orders.py` (12 tests): Status dimension parsing, GST tolerance, and messy number cleaning.
- `test_quality_report.py` (8 tests): Column completeness and cross-board data quality profiling.
- Additional test modules covering edge cases, configuration, and API models.
