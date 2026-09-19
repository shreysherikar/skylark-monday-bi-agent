# Monday.com Board Setup Guide

This guide outlines how to import the provided source datasets into Monday.com boards with appropriate column types and structure.

---

## 1. Work Orders Board (`work order tracker`)

### Source File Preprocessing Before Import:
- Note that the raw Excel file has **Row 1 completely blank**.
- **Row 2** contains the actual 38 column headers.
- **Rows 3–178** contain the 176 data rows.
- If exporting to CSV or importing to Monday.com, set row 2 as the header row (skip blank row 1).

### Recommended Monday.com Column Types:

| Column Name | Suggested Monday Column Type | Notes |
|---|---|---|
| `Deal name masked` | Text / Item Name | Primary deal name identifier |
| `Customer Name Code` | Text | Formatted as `WOCOMPANY_xxx` |
| `Serial #` | Text | Unique identifier `SDPLDEAL-xxx` (176 unique values) |
| `Nature of Work` | Status / Dropdown | One time Project, Proof of Concept, Monthly Contract, Annual Rate Contract |
| `Last executed month of recurring project` | Text / Dropdown | Sparsely populated (15 rows) |
| `Execution Status` | Status | Completed, Ongoing, Executed until current month, Not Started, etc. |
| `Data Delivery Date` | Date | Sparsely populated (58 rows) |
| `Date of PO/LOI` | Date | Almost fully populated (175 rows) |
| `Document Type` | Status / Dropdown | Purchase Order, Email Confirmation, LOA/LOI |
| `Probable Start Date` | Date | 158 rows populated |
| `Probable End Date` | Date | 157 rows populated |
| `BD/KAM Personnel code` | Text / People | Formatted as `OWNER_xxx` |
| `Sector` | Status / Dropdown | Mining, Renewables, Railways, Powerline, Others, Construction |
| `Type of Work` | Text / Dropdown | Specific service delivery type (36 variations) |
| `Is any Skylark software platform...` | Status / Dropdown | NONE, SPECTRA, DMO, SPECTRA + DMO |
| `Last invoice date` | Date | 87 rows populated |
| `latest invoice no.` | Text | Invoice reference string |
| `Amount in Rupees (Excl of GST) (Masked)` | Numbers | Contract value excl GST |
| `Amount in Rupees (Incl of GST) (Masked)` | Numbers | Contract value incl GST |
| `Billed Value in Rupees (Excl of GST.) (Masked)` | Numbers | Note: unbilled rows are blank, not 0 |
| `Billed Value in Rupees (Incl of GST.) (Masked)` | Numbers | Note: unbilled rows are 0 |
| `Collected Amount in Rupees (Incl of GST.) (Masked)` | Numbers | Uncollected rows are blank |
| `Amount to be billed in Rs. (Exl. of GST) (Masked)` | Numbers | Contains valid negative values |
| `Amount to be billed in Rs. (Incl. of GST) (Masked)` | Numbers | Contains valid negative values |
| `Amount Receivable (Masked)` | Numbers | Contains valid negative values |
| `AR Priority account` | Status | 'Priority' or blank |
| `Quantity by Ops` | Numbers | Operational execution quantity |
| `Quantities as per PO` | Text | Free text mixing numbers and units (e.g. "5360 HA") |
| `Quantity billed (till date)` | Numbers | Sparsely populated (23 rows) |
| `Balance in quantity` | Numbers | Balance remaining; contains negative values |
| `Invoice Status` | Status | Fully Billed, Partially Billed, Not billed yet, etc. |
| `Expected Billing Month` | Text / Date | Currently 100% empty in sample |
| `Actual Billing Month` | Text / Dropdown | July, August, June, etc. (70 rows) |
| `Actual Collection Month` | Text / Date | Currently 100% empty in sample |
| `WO Status (billed)` | Status | Open, Closed |
| `Collection status` | Status | Currently 100% empty in sample |
| `Collection Date` | Date | Currently 100% empty in sample |
| `Billing Status` | Status | Update Required, Not Billable, Partially Billed, BIlled, Stuck |

---

## 2. Deals Board (`Deal tracker`)

### Source File Preprocessing Before Import:
- Total rows: 347 (Row 1 is headers).
- **CRITICAL**: Rows 52 and 181 (data index 50 and 179) are **duplicate header rows** embedded in the data. Filter these out before import, or delete them in Monday.com after import.
- Actual data rows: 344 records.

### Recommended Monday.com Column Types:

| Column Name | Suggested Monday Column Type | Notes |
|---|---|---|
| `Deal Name` | Text / Item Name | Non-unique (repeats across clients) |
| `Owner code` | Text / People | Formatted as `OWNER_xxx` |
| `Client Code` | Text | Formatted as `COMPANYxxx` |
| `Deal Status` | Status | Won, Dead, Open, On Hold |
| `Close Date (A)` | Date | Sparsely populated (26 valid dates) |
| `Closure Probability` | Status / Dropdown | High, Medium, Low (75% blank) |
| `Masked Deal value` | Numbers | Deal pipeline value (52% blank) |
| `Tentative Close Date` | Date | Projected close date |
| `Deal Stage` | Status / Dropdown | 16 stages (ordered funnel A through O + Project Completed) |
| `Product deal` | Text / Dropdown | Pure Service, Service + Spectra, etc. |
| `Sector/service` | Status / Dropdown | Industry sector (contains non-sectors like Tender, DSP) |
| `Created Date` | Date | Deal creation timestamp |

---

## 3. Linking Work Orders to Deals via "Connect Boards" Column

Because no foreign key (`Serial #` or clean Deal ID) exists in the raw Deals board as exported, cross-board linking must be established **before or during board import** rather than relying on ambiguous heuristic joins at agent query time.

### Step 1: Run Offline Matching Script
Execute the pre-import offline matching script:
```bash
python scripts/build_deal_links.py
```
This generates `scripts/deal_wo_links.csv` containing:
- `wo_serial`: Work Order serial number
- `matched_deal_row_id`: Logical item ID of the matched deal in the Deals board
- `matched_deal_name`: Deal name
- `matched_client_code`: Client code
- `confidence_tier`: `MATCHED_HIGH`, `MATCHED_FUZZY`, or `UNMATCHED`
- `match_notes`: Rationale for the match / reasons for unmatched status

### Step 2: Configure Monday.com "Connect Boards" Column
1. On the **Work Orders board**, add a new column of type **Connect Boards**.
2. Select the **Deals board** as the target board.
3. Name the column: `Linked Deal`.
4. Optionally enable **Mirror Columns** on Work Orders to display:
   - `Deal Stage` (from Deals board)
   - `Closure Probability` (from Deals board)
   - `Masked Deal value` (from Deals board)

### Step 3: Populate the Relation
- When importing the Work Orders CSV, include `matched_deal_name` or `matched_deal_row_id` as the source for the `Linked Deal` Connect Boards column for rows in `MATCHED_HIGH` and `MATCHED_FUZZY`.
- Leave `Linked Deal` blank for rows categorized as `UNMATCHED`.
- Add a custom status column `Link Confidence` (`MATCHED_HIGH`, `MATCHED_FUZZY`, `UNMATCHED`) to Work Orders so executives and the agent can immediately inspect the link confidence on any record.

