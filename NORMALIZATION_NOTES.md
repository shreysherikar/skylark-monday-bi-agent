# Data Normalization Notes & Column-by-Column Audit

This document is the **source of truth** for data patterns, edge cases, and cleaning rules that must be implemented by `backend/app/data/normalize_work_orders.py` and `backend/app/data/normalize_deals.py`.

---

## 1. Corrections and Additions to PROJECT_PLAN.md §2

Direct inspection of both `Work_Order_Tracker Data.xlsx` and `Deal funnel Data.xlsx` reveals several critical discrepancies, corrections, and additions to the baseline assumptions in §2 of the project plan:

### 1.1 Summary of Corrections to §2
| Topic | Documented in §2 | Ground Truth in Data | Impact / Action Required |
|---|---|---|---|
| **Work Orders Row Count** | 177 data rows | **176 data rows** | Excel Row 1 is completely empty (`None` across all cols). Row 2 contains headers. Rows 3–178 contain 176 data rows. |
| **Deals Row Count** | 346 data rows | **344 actual records** (2 embedded header rows) | Excel has 347 rows. Data rows 50 and 179 (Excel rows 52 and 181) are **duplicate header rows** (`Deal Status == 'Deal Status'`, `Deal Stage == 'Deal Stage'`, etc.). Must be filtered out. |
| **Join Key (`Serial #`)** | "The only clean join key back to the Deals board" | **`Serial #` DOES NOT EXIST in the Deals board!** | In WO, `Serial #` is 100% populated (`SDPLDEAL-001` to `SDPLDEAL-176`). But in Deals, there are only 12 columns, none of which contain `Serial #` or `SDPLDEAL`. |
| **Alternative Join: `(Deal Name, Client Code)`** | Noted that `(Deal Name, Client Code)` is unique | **Only 1 record matches** composite `(Deal Name, Client Code)` | WO has `Deal name masked` and `Customer Name Code` (`WOCOMPANY_xxx`). Deals has `Deal Name` and `Client Code` (`COMPANYxxx`). Normalizing `WOCOMPANY_` -> `COMPANY` yields only 1 composite match (`Appa`, `COMPANY038`). Deal names overlap (52 shared names), but are reused across different clients. |
| **`Quantities as per PO`** | Free text mixing numbers and units (`5360 HA`, `4`, `59.33`) | **71 non-numeric string variants** with complex syntax | Contains attached units (`115HA`, `40MW`), commas (`1,310.850`), ranges/slabs, typos (`415Acers`, `2057 Acr`), abbreviations, and non-quantitative strings (`L/s`, `Rate based on MW slabs`). |
| **Legitimate Negative Values** | Mentioned in `Amount to be billed` (−₹82,907.30) | **Present in 3 distinct fields (4 columns)**, not just one! | 1. `Amount to be billed (Excl of GST)`: 6 negative rows (min: −₹82,907.30).<br>2. `Amount to be billed (Incl of GST)`: 6 negative rows (min: −₹97,830.61).<br>3. `Amount Receivable (Masked)`: 11 negative rows (min: −₹160.24).<br>4. `Balance in quantity`: 2 negative rows (−0.01, −1,309.85). |
| **Status Vocabularies** | Listed partial vocabularies for 4 columns | **Significantly richer vocabularies** | `Execution Status` has 7 distinct values (not 3); `Invoice Status` has 6 values; `WO Status (billed)` has 2; `Billing Status` has 5 (and is 84% null). |
| **Entirely Empty Columns** | Not mentioned | **4 columns in WO are 100% NULL (176/176)** | `Expected Billing Month`, `Actual Collection Month`, `Collection status`, `Collection Date`. |
| **Deals Null Rates** | Mentioned `Closure Probability` frequently blank | **Severe null rates across multiple core fields** | `Close Date (A)` is **92.4% null** (only 26 dates). `Closure Probability` is **75.0% null**. `Masked Deal value` is **52.0% null**. `Product deal` is **49.4% null**. |

---

## 2. The Join Key Reality & Strategy

### The Problem
`PROJECT_PLAN.md` §2 originally assumed `Serial #` (`SDPLDEAL-xxx`) was present on both boards. In the actual dataset:
1. In `Work_Order_Tracker Data.xlsx`, `Serial #` is populated on 100% of rows (all 176 unique, spanning `SDPLDEAL-001` to `SDPLDEAL-189` with 13 numbers unassigned).
2. In `Deal funnel Data.xlsx`, there is **no `Serial #` column** or any string containing `SDPLDEAL`.
3. If matching by `Deal Name` alone: Deal names are reused across clients (e.g., `Sakura` appears 10 times in Deals and 9 times in WO; `Naruto` appears 11 times in Deals and 1 time in WO).
4. If matching by `(Deal Name, Client Code)` (normalizing `WOCOMPANY_xxx` -> `COMPANYxxx`): only **1 out of 176 work orders matches** (`Appa` with `COMPANY038`).
5. In Deals, 165 records have `Deal Status == 'Won'`, which closely parallels the 176 Work Orders, but there is no explicit foreign key link in the provided raw files.

### Pre-Import Offline Matching Architecture (`scripts/build_deal_links.py`)
To solve this cleanly before data is imported into Monday.com:
- An offline linking script (`scripts/build_deal_links.py`) runs **before** board creation.
- It attempts multi-feature resolution using:
  - `Deal Name` (exact match or normalized case)
  - Normalized customer code (`WOCOMPANY_xxx` -> `COMPANYxxx`)
  - `Sector` alignment (`Mining`, `Powerline`, `Renewables`, `Railways`, etc.)
  - Date proximity (Work Order `Date of PO/LOI` vs Deals `Created Date` and `Close Date (A)`)
  - Personnel alignment (WO `BD/KAM Personnel code` vs Deals `Owner code`)
- Output: A mapping file (`scripts/deal_wo_links.csv`) containing `Serial #`, `Deal Name (WO)`, `Matched Deal Name (Deals)`, `Deal Index/ID`, `Confidence Tier`, and `Match Notes`.
- **Confidence Tiers**:
  - `MATCHED_HIGH`: Exact Deal Name + Normalized Client Code match, OR exact Deal Name + matching Sector + matching Owner code + close date proximity (within window).
  - `MATCHED_FUZZY`: Exact Deal Name + matching Sector (when Deal Name is unique or unambiguous within sector), OR high date proximity + matching Sector + matching Owner.
  - `UNMATCHED`: Ambiguous multiple candidates, non-overlapping sectors/names, or missing critical fields. *UNMATCHED is a valid, expected outcome for unlinked records.*
- **Monday.com Integration**: The resulting mapping file is used during board setup to populate a native Monday.com **"Connect Boards"** column linking Work Orders to Deals directly.
- **Normalization & Analytics Layer**: `join_work_orders_to_deals` reads this native relation or mapping, always returning:
  `(matched_df, unmatched_wo_df, unmatched_deal_df)`. Every cross-board analytics function reports the match statistics to the agent for caveat narration.

---

## 3. Work Orders Board (`work order tracker`) — Column Inventory

Total rows: 178 in Excel.
- Excel Row 1: Completely empty.
- Excel Row 2: 38 Column Headers.
- Excel Rows 3–178: Exactly **176 data rows**.

| # | Column Name | Raw Type | Target Type | Non-Null | Null (%) | Unique | Observed Values / Messiness & Normalization Rule |
|---|---|---|---|---|---|---|---|
| 1 | `Deal name masked` | str | `str` | 175 | 0.6% | 58 | Anime / character names (`Scooby-Doo`, `Sakura`, `Naruto`). 1 row is null. Strip whitespace. |
| 2 | `Customer Name Code` | str | `str` | 176 | 0.0% | 51 | Formatted as `WOCOMPANY_001` through `WOCOMPANY_051`. 100% populated. Clean representation: retain original, add `client_code_normalized` (`COMPANYxxx`). |
| 3 | `Serial #` | str | `str` | 176 | 0.0% | 176 | Format `SDPLDEAL-001` to `SDPLDEAL-189` (176 unique values across span 1–189; 13 unassigned serial numbers). Primary key in WO. |
| 4 | `Nature of Work` | str | `Enum` | 164 | 6.8% | 4 | Values: `One time Project` (125), `Proof of Concept` (15), `Annual Rate Contract` (14), `Monthly Contract` (10). 12 nulls -> `UNKNOWN`. |
| 5 | `Last executed month of recurring project` | str | `str \| None` | 15 | 91.5% | 5 | Sparsely populated: `Dec` (5), `June` (4), `November` (3), `May` (2), `March` (1). 161 nulls. Normalize month abbreviations. |
| 6 | `Execution Status` | str | `Enum` | 172 | 2.3% | 7 | Values: `Completed` (117), `Ongoing` (25), `Executed until current month` (12), `Not Started` (11), `Pause / struck` (4), `Partial Completed` (2), `Details pending from Client` (1). 4 nulls -> `UNKNOWN`. |
| 7 | `Data Delivery Date` | Timestamp | `date \| None` | 58 | 67.0% | 42 | Range: 2025-01-23 to 2026-01-09. 118 nulls. Parse to ISO date. |
| 8 | `Date of PO/LOI` | Timestamp | `date \| None` | 175 | 0.6% | 103 | Range: 2022-09-29 to 2026-01-12. 1 null. Primary booking/order date. |
| 9 | `Document Type` | str | `Enum` | 162 | 8.0% | 3 | Values: `Purchase Order` (141), `Email Confirmation` (11), `LOA/LOI` (10). 14 nulls -> `UNKNOWN`. |
| 10 | `Probable Start Date` | Timestamp | `date \| None` | 158 | 10.2% | 87 | Range: 2024-07-30 to 2026-01-19. 18 nulls. |
| 11 | `Probable End Date` | Timestamp | `date \| None` | 157 | 10.8% | 75 | Range: 2025-04-10 to 2028-03-31. 19 nulls. |
| 12 | `BD/KAM Personnel code` | str | `str \| None` | 165 | 6.2% | 7 | Values: `OWNER_001` to `OWNER_006`, `OWNER_008`. 11 nulls. |
| 13 | `Sector` | str | `Enum` | 176 | 0.0% | 6 | Values: `Mining` (100), `Renewables` (51), `Railways` (13), `Powerline` (6), `Others` (4), `Construction` (2). 100% non-null. |
| 14 | `Type of Work` | str | `str` | 176 | 0.0% | 36 | Work deliverables: `Raw images/videography`, `Powerline Inspection`, `Volumetric survey`, `Topography Survey: RGB`, `Hydrology`, etc. 100% non-null. |
| 15 | `Is any Skylark software platform...` | str | `Enum` | 164 | 6.8% | 4 | Values: `NONE` (134), `SPECTRA` (16), `DMO` (10), `SPECTRA + DMO` (4). 12 nulls -> `NONE`. |
| 16 | `Last invoice date` | Timestamp | `date \| None` | 87 | 50.6% | 44 | Range: 2025-03-31 to 2026-01-14. 89 nulls (unbilled or unrecorded). |
| 17 | `latest invoice no.` | str | `str \| None` | 88 | 50.0% | 86 | Format: `SDPL/FY25-26/xxx`. 88 nulls. |
| 18 | `Amount in Rupees (Excl of GST) (Masked)` | float | `float \| None` | 175 | 0.6% | 145 | 1 null, 6 zeros, 169 positive. Min: 0, Max: ₹57,487,090.49. |
| 19 | `Amount in Rupees (Incl of GST) (Masked)` | float | `float` | 176 | 0.0% | 145 | 7 zeros, 169 positive. 100% non-null. Rate of GST is 18% (`Incl = Excl * 1.18`). |
| 20 | `Billed Value in Rupees (Excl of GST.) (Masked)` | float | `float \| None` | 113 | 35.8% | 100 | **63 nulls, 0 zeros**. When unbilled, column is `null`, NOT `0`. |
| 21 | `Billed Value in Rupees (Incl of GST.) (Masked)` | float | `float` | 176 | 0.0% | 101 | **63 zeros, 0 nulls**. Corresponds to col 20 multiplied by 1.18, with nulls imputed as 0. |
| 22 | `Collected Amount in Rupees (Incl of GST.) (Masked)` | float | `float \| None` | 78 | 55.7% | 76 | **98 nulls, 0 zeros**. When uncollected, column is `null`. Range: ₹2,467.63 to ₹57,487,090.49. |
| 23 | `Amount to be billed in Rs. (Exl. of GST) (Masked)` | float | `float` | 176 | 0.0% | 99 | **6 negative values** (min: −₹82,907.30), 70 zeros, 100 positive. Negative indicates billed > contracted. |
| 24 | `Amount to be billed in Rs. (Incl. of GST) (Masked)` | float | `float` | 176 | 0.0% | 99 | **6 negative values** (min: −₹97,830.61), 70 zeros, 100 positive. |
| 25 | `Amount Receivable (Masked)` | float | `float` | 176 | 0.0% | 96 | **11 negative values** (min: −₹160.24), 77 zeros, 88 positive. Represents `Billed - Collected`. Negative represents minor overpayment/credit balance. |
| 26 | `AR Priority account` | str | `bool` | 10 | 94.3% | 1 | Values: `'Priority'` (10 rows), 166 nulls. Normalize to boolean (`True` if Priority else `False`). |
| 27 | `Quantity by Ops` | float | `float \| None` | 43 | 75.6% | 43 | 43 positive floats, 133 nulls. Min: 49.49, Max: 6539.58. |
| 28 | `Quantities as per PO` | str | `ParsedQuantity` | 160 | 9.1% | 118 | **Free text mixing numbers and units** (71 non-numeric string patterns). See §4 for parser specification. 16 nulls. |
| 29 | `Quantity billed (till date)` | float | `float \| None` | 23 | 86.9% | 17 | 23 positive floats, 153 nulls. Min: 1.0, Max: 3956.0. |
| 30 | `Balance in quantity` | float | `float \| None` | 157 | 10.8% | 95 | **2 negative values** (−0.01, −1309.85), 13 zeros, 142 positive. 19 nulls. |
| 31 | `Invoice Status` | str | `Enum` | 112 | 36.4% | 6 | Values: `Fully Billed` (91), `Partially Billed` (10), `Not billed yet` (8), `Billed- Visit 7` (1), `Billed- Visit 3` (1), `Stuck` (1). 64 nulls -> `NOT_BILLED` or `UNKNOWN`. |
| 32 | `Expected Billing Month` | None | `None` | 0 | **100.0%** | 0 | **Entirely empty column (176 nulls)**. Preserved in schema as all-null. |
| 33 | `Actual Billing Month` | str | `str \| None` | 70 | 60.2% | 7 | Values: `July` (27), `August` (14), `June` (12), `September` (9), `November` (5), `Dec` (2), `October` (1). 106 nulls. Normalize to standard month names. |
| 34 | `Actual Collection Month` | None | `None` | 0 | **100.0%** | 0 | **Entirely empty column (176 nulls)**. Preserved in schema as all-null. |
| 35 | `WO Status (billed)` | str | `Enum` | 102 | 42.0% | 2 | Values: `Closed` (78), `Open` (24). 74 nulls -> `UNKNOWN`. |
| 36 | `Collection status` | None | `None` | 0 | **100.0%** | 0 | **Entirely empty column (176 nulls)**. Preserved in schema as all-null. |
| 37 | `Collection Date` | None | `None` | 0 | **100.0%** | 0 | **Entirely empty column (176 nulls)**. Preserved in schema as all-null. |
| 38 | `Billing Status` | str | `Enum` | 28 | 84.1% | 5 | Values: `Update Required` (12), `Not Billable` (7), `Partially Billed` (3), `BIlled` (3, typo with uppercase I), `Stuck` (3). 148 nulls. Normalize `BIlled` -> `BILLED`. |

---

## 4. Deep Dive: Parsing `Quantities as per PO`

The column `Quantities as per PO` contains 160 non-null values exhibiting 5 distinct structural patterns:

```
                                  Quantities as per PO (160 rows)
                                              │
         ┌──────────────────┬─────────────────┴─────────────────┬──────────────────┐
         ▼                  ▼                                   ▼                  ▼
    Pure Numeric      Number + Unit                       NumberAttachedUnit   Unparseable /
     (89 rows)          (43 rows)                             (19 rows)         Qualitative
     e.g. 4, 3000,      e.g. "5360 HA", "10.5 KM",           e.g. "115HA",       (9 rows)
     59.33, 1,310.85    "200 Acres", "7000 images"           "40MW", "45days"    "L/s", "MW slabs"
```

### 4.1 Parser Specification (`parse_po_quantity`)
Return type: `NamedTuple(value: Optional[float], unit: Optional[str], raw: str, is_qualitative: bool)`

1. **Pure Numerics**:
   - `4`, `3000`, `600`, `59.33` -> `value=float`, `unit=None`
   - Comma-formatted numbers: `"1,310.850"`, `"4,875,000.000"` -> strip commas, cast to float.
2. **Standard Units (with space)**:
   - Regex: `r"^\s*([\d,]+(?:\.\d+)?)\s+([A-Za-z/]+(?:\s+[A-Za-z]+)?)\s*$"`
   - Patterns: `"5360 HA"`, `"10.5 KM"`, `"104 km"`, `"1415 Acres"`, `"7000 images"`, `"1250 towers"`, `"45 days"`, `"18 Months"`, `"3 subscriptions"`, `"4 Sites"`, `"3 Rooftops"`, `"7 mines"`, `"36 AU"`, `"145 pillars"`, `"2 location"`.
3. **Attached Units (without space)**:
   - Regex: `r"^\s*([\d,]+(?:\.\d+)?)\s*([A-Za-z]+.*)$"`
   - Patterns: `"115HA"`, `"220HA"`, `"3956HA"`, `"660.43HA"`, `"497Acres"`, `"230Acres"`, `"415Acers"`, `"2057 Acr"`, `"40MW"`, `"45days"`.
   - Normalization of units:
     - `HA`, `Ha`, `ha` -> `"HA"` (Hectares)
     - `Acres`, `Acers`, `Acr` -> `"Acres"`
     - `KM`, `km`, `RKM` -> `"KM"` / `"RKM"` (Route Kilometers)
     - `days`, `45days` -> `"days"`
     - `months`, `Months` -> `"months"`
     - `towers`, `Towers` -> `"towers"`
4. **Descriptive / Qualitative Strings (Cannot extract single volume)**:
   - `"L/s"` -> Lump Sum (`value=None`, `unit="L/s"`, `is_qualitative=True`)
   - `"Rate based on MW slabs"` -> (`value=None`, `unit="MW slabs"`, `is_qualitative=True`)
   - `"NA . Verbal confirmation for 59 km"` -> extract `value=59.0`, `unit="KM"`, flag caveat.
   - `"3 Quarter (Till Dec)"`, `"3 Quarter (till December 2025)"` -> `value=3.0`, `unit="Quarter"`.
5. **Nulls**:
   - `None` or `NaN` -> `value=None`, `unit=None`.

---

## 5. Status Orthogonality in Work Orders

The 4 status fields in Work Orders measure completely different stages of lifecycle:

1. **`Execution Status` (Operational fulfillment)**:
   - `Completed`: Work on the ground is finished.
   - `Ongoing`: Drones/teams are actively operating.
   - `Executed until current month`: Recurring work completed through current cycle.
   - `Not Started`: Scheduled but no field activity.
   - `Pause / struck`: Work temporarily halted.
   - `Partial Completed`: Only part of the scope completed.
   - `Details pending from Client`: Blocked by client dependencies.
2. **`Invoice Status` (Billing execution stage)**:
   - `Fully Billed`: All contract value has been invoiced.
   - `Partially Billed`: Milestones invoiced, remaining unbilled.
   - `Not billed yet`: Zero invoices generated.
   - `Billed- Visit 7` / `Billed- Visit 3`: Milestone-based billing labels.
   - `Stuck`: Invoicing blocked or rejected.
3. **`WO Status (billed)` (Administrative account closure)**:
   - `Closed`: Work order fully reconciled and closed in ERP.
   - `Open`: Work order remains administratively active.
4. **`Billing Status` (Billing exception handling)**:
   - Populated on only 28 rows (84% null).
   - `Update Required`: Billing paperwork needs manual revision.
   - `Not Billable`: Zero-value POC or non-chargeable work.
   - `BIlled`: Typo in legacy record; represents billed.
   - `Stuck`: Invoice processing exception.

**Normalization Rule**: Never merge these into a single "status" field. Model each as a distinct typed enum.

---

## 6. Deals Board (`Deal tracker`) — Column Inventory

Total rows: 347 in Excel.
- Row 1: 12 Column Headers.
- **Rows 50 and 179**: Embedded header rows (`Deal Status == 'Deal Status'`). Filter out!
- Actual records: **344 deals**.

| # | Column Name | Raw Type | Target Type | Non-Null | Null (%) | Unique | Observed Values / Messiness & Normalization Rule |
|---|---|---|---|---|---|---|---|
| 1 | `Deal Name` | str | `str` | 342 | 0.6% | 154 | Anime / pop culture names (`Naruto`, `Sasuke`, `Sakura`, `Kakashi`). Non-unique (repeats across clients). 2 rows in data are null (`NaN`). |
| 2 | `Owner code` | str | `str \| None` | 329 | 4.4% | 7 | Format: `OWNER_001` to `OWNER_007`. 15 nulls in data. |
| 3 | `Client Code` | str | `str` | 344 | 0.0% | 199 | Format: `COMPANY001` to `COMPANY199`. 100% non-null (excluding header rows). |
| 4 | `Deal Status` | str | `Enum` | 343 | 0.3% | 4 | Values: `Won` (165), `Dead` (127), `Open` (49), `On Hold` (2). 1 null row (`Tanjiro`, `COMPANY038`). Clean enum. |
| 5 | `Close Date (A)` | Timestamp | `date \| None` | 26 | **92.4%** | 17 | Actual Close Date. Only 26 deals have this populated! Range: 2024-12-31 to 2026-01-15. 318 nulls. |
| 6 | `Closure Probability` | str | `Enum \| None` | 86 | **75.0%** | 3 | Values: `High` (48), `Medium` (22), `Low` (16). **258 nulls (75%)**. Never default null to Medium/Low; flag data quality caveats in weighted pipeline queries. |
| 7 | `Masked Deal value` | float | `float \| None` | 165 | **52.0%** | 103 | Deal pipeline amount. **179 nulls (52%)**. All positive numbers (Min: ₹51,440.30, Max: ₹751,473,450.00). |
| 8 | `Tentative Close Date` | Timestamp | `date \| None` | 270 | 21.5% | 78 | Projected close date. Range: 2024-09-30 to 2026-04-01. 74 nulls. |
| 9 | `Deal Stage` | str | `Enum` | 344 | 0.0% | 16 | 16 distinct stages (ordered funnel A through O, plus `Project Completed`). 100% non-null. See §7 for stage definitions. |
| 10 | `Product deal` | str | `Enum \| None` | 174 | 49.4% | 9 | Values: `Pure Service` (151), `Service + Spectra` (12), `Dock + DMO + Spectra + Service` (3), `Spectra Deal` (3), `Spectra + DMO` (1), `Hardware` (1), `Dock + Spectra + Service` (1), `Dock + DMO + Spectra` (1), `Dock + DMO` (1). 170 nulls. |
| 11 | `Sector/service` | str | `Enum` | 336 | 2.3% | 11 | Contains legitimate sectors AND operational classifications (`Tender`, `DSP`). 8 nulls. See §8 for handling. |
| 12 | `Created Date` | Timestamp | `date \| None` | 343 | 0.3% | 83 | Deal creation date. Range: 2024-08-09 to 2026-01-09. 1 null row (`Sakura`, `COMPANY149`). |

---

## 7. Deals Board: Stage Hierarchy & Funnel Ordering

The `Deal Stage` field uses letter prefixes (`A.` through `O.`) to denote funnel progression, with one unlettered stage (`Project Completed`):

```
Active Sales Funnel (In Progress)
  ├── A. Lead Generated (74)
  ├── B. Sales Qualified Leads (14)
  ├── C. Demo Done (9)
  ├── D. Feasibility (4)
  ├── E. Proposal/Commercials Sent (28)
  └── F. Negotiations (13)

Won / Executing
  ├── G. Project Won (27)
  ├── H. Work Order Received (46)
  ├── I. POC (3)
  ├── J. Invoice sent (6)
  ├── K. Amount Accrued (2)
  └── Project Completed (19)

Dormant / Lost
  ├── L. Project Lost (42)
  ├── M. Projects On Hold (20)
  ├── N. Not relevant at the moment (19)
  └── O. Not Relevant at all (18)
```

**Normalization Rule**:
Define a stage classification mapping:
- `is_active_pipeline`: Stages A through F
- `is_won`: Stages G, H, I, J, K, and `Project Completed`
- `is_lost_or_dormant`: Stages L, M, N, O
When aggregating "active pipeline value", only include `is_active_pipeline` stages with positive deal values.

---

## 8. Sector Vocabularies & Non-Sector Value Handling

### Deals Board `Sector/service`:
- Standard Sectors:
  - `Renewables` (111)
  - `Mining` (106)
  - `Railways` (40)
  - `Powerline` (26)
  - `Construction` (9)
  - `Manufacturing` (2)
  - `Security and Surveillance` (1)
  - `Aviation` (1)
  - `Others` (28)
- Non-Sector Classifications:
  - `Tender` (5 rows): Government or enterprise bidding process.
  - `DSP` (7 rows): Drone Service Provider delivery model.
- Nulls: 8 rows.

### Work Orders Board `Sector`:
- `Mining` (100)
- `Renewables` (51)
- `Railways` (13)
- `Powerline` (6)
- `Others` (4)
- `Construction` (2)

**Normalization Rule**:
When queries ask for sectoral breakdown:
- Filter or tag `Tender` and `DSP` as `Procurement/Delivery Channel` rather than industry sector, or classify under `Others (Tender)` / `Others (DSP)`.
- Support fuzzy matching for queries ("energy" -> `Renewables`, "mines" -> `Mining`, "trains" -> `Railways`).

---

## 9. Data Quality Flags & Caveat Trigger Rules

The agent must not state bare aggregations as undisputed facts when data quality issues affect the result. The normalization layer must generate a `QualityReport` with specific metrics:

1. **Weighted Pipeline Calculation**:
   - **Trigger**: Query asks for weighted pipeline.
   - **Caveat**: `Closure Probability` is missing on 75% of deals (258/344). State:
     > *"Note: 75% of deals do not have a closure probability assigned. Weighted pipeline is calculated solely on the 86 deals with probability set, representing ₹X of ₹Y total pipeline."*
2. **Deal Values Missing**:
   - **Trigger**: Query asks for total pipeline value.
   - **Caveat**: 52% of deals have missing `Masked Deal value`. State:
     > *"Note: Deal value is unrecorded for 179 of 344 deals (52%). Actual pipeline is likely significantly higher."*
3. **Cross-Board Joins (Work Orders ↔ Deals)**:
   - **Trigger**: Query spans both boards (e.g. "Work orders delivered vs pipeline for mining").
   - **Caveat**: `Serial #` is absent in Deals data; composite matching yields limited links. State:
     > *"Data quality caveat: Work orders and deals lack an explicit foreign key. Analysis reflects X matched records; unlinked work orders (Y) and deals (Z) are reported separately."*
4. **Receivables & Negative Values**:
   - **Trigger**: Query asks for outstanding receivables or billing balance.
   - **Caveat**: Preserve negative balances and explicitly note:
     > *"6 work orders have negative billing balances (billed value exceeds contract value by ₹X), and 11 accounts show net credit balances in receivables (totaling ₹Y)."*
5. **Completely Empty Columns**:
   - **Trigger**: Query asks about expected billing dates or collection statuses in Work Orders.
   - **Caveat**: Report:
     > *"The columns 'Expected Billing Month', 'Actual Collection Month', 'Collection status', and 'Collection Date' contain no recorded data in the source board."*
