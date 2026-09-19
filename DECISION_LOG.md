# Decision Log: Skylark Drones Monday.com BI Agent

> Note: Kept updated throughout development phases. Target length ≤ 2 pages.

## 1. Key Assumptions & Ground Truth Join Strategy
- **Join Key Reality**: `Serial #` (`SDPLDEAL-xxx`) is 100% present in Work Orders, but completely absent from the Deals board. Furthermore, composite `(Deal Name, Client Code)` matching yields only 1 match due to disparate client numbering.
- **Offline Resolution Pre-Import**: Implemented a deterministic pre-import matching script (`scripts/build_deal_links.py`) utilizing multi-feature scoring (Deal Name, normalized client code, sector, owner code, won status, and PO-to-deal date proximity). Matches are categorized into confidence tiers (`MATCHED_HIGH`, `MATCHED_FUZZY`, `UNMATCHED`) and output as `scripts/deal_wo_links.csv` to establish a native Monday.com "Connect Boards" relation column (`Linked Deal`) upon board creation.
- **Ambiguous Column Interpretations**:
  - Blank string `''` / `null` is distinct from `0`. Unreported numeric values are not coerced to `0` without explicit caveats.
  - Negative values across **three fields** (comprising four numeric columns) are preserved as legitimate business conditions:
    - `Amount to be billed in Rs. (Exl. of GST) (Masked)`: 6 negative rows, min −₹82,907.30
    - `Amount to be billed in Rs. (Incl. of GST) (Masked)`: 6 negative rows, min −₹97,830.61
    - `Amount Receivable (Masked)`: 11 negative rows, min −₹160.24 (overpayments, credit balances, minor rounding)
    - `Balance in quantity`: 2 negative rows, min −1,309.85 (−0.01 and −1,309.85; execution/billed volume exceeded estimate)
  - Quantity fields containing units (`Quantities as per PO` with 71 non-numeric variants) are parsed into numeric quantity and unit string.
  - Four status columns (`Execution Status`, `Invoice Status`, `WO Status (billed)`, `Billing Status`) represent orthogonal dimensions and are preserved separately.
  - Four columns in Work Orders (`Expected Billing Month`, `Actual Collection Month`, `Collection status`, `Collection Date`) are 100% NULL (176/176) in the source data.
- **Controlled Vocabularies & Enums**: Non-sector values in Deals (`Tender`, `DSP`) and unknown categories fall into `UNKNOWN` / categorized buckets with tracking for quality reporting.

## 2. Trade-offs & Scope Calibration (against 6-hour target)
- **Architecture & Infrastructure**: Focused on depth and correctness of data normalization, query accuracy, and prompt resilience rather than multi-service cloud infrastructure sprawl. Using a single containerized FastAPI backend with AWS App Runner deployment.
- **Database / Storage**: Monday.com is the single source of truth queried dynamically (cached in-memory with a short 5-minute TTL). Avoided persistent external databases like RDS to respect the assignment constraints.
- **MCP Pattern**: Implemented custom read-only MCP server wrapper over Monday.com GraphQL API for structured schema introspection and tool execution.

## 3. What We Would Do Differently With More Time
- Implement incremental sync or webhook-based cache invalidation from monday.com boards.
- Work with business owners to resolve the 93 ambiguous multi-candidate deal rows that share identical character names, sectors, and owners.
- Add richer charting and export capabilities (PDF/slides) for leadership reports.

## 4. Interpretation of "Leadership Updates"
- Interpreted as a structured weekly/monthly executive briefing:
  - Billed vs. collected revenue vs. receivables
  - Sales pipeline by deal stage and sector
  - Delivery and execution health (completed vs. in-progress work orders)
  - Data quality risks and confidence flags
  - Formatted in clean Markdown for copy-pasting directly into leadership memos, emails, or Slack.

## 5. Known Limitations
- **Join Match Rate**: Only 15 of 176 Work Orders (8.5%) can be linked with High (6, 3.4%) or Fuzzy (9, 5.1%) confidence without manual disambiguation. 161 Work Orders (91.5%) remain `UNMATCHED` due to identical duplicated deal names across different deals (93 rows), dead deal statuses in CRM (52 rows), sector conflicts (9 rows), deal names absent from the Deals board (6 rows), and 1 row missing a deal name entirely (93 + 52 + 9 + 6 + 1 = 161).
- **High Null Rates in Deals**: `Close Date (A)` is 92.4% null (318/344), `Closure Probability` is 75.0% null (258/344), and `Masked Deal value` is 52.0% null (179/344); all pipeline figures must carry data quality caveats.
- **Free-form PO Quantities**: Legacy records contain qualitative entries like "L/s" (lump sum) or "Rate based on MW slabs" where numeric volume cannot be extracted.
