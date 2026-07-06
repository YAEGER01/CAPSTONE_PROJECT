# Membership Payment System — Detailed Implementation Plan

> Based on analysis of Treasurer, Auditor, and President workflows vs. existing codebase.

---

## Phase 1: Foundational (Department Compliance Engine)

---

### 1.1 Create `Department` model

**Goal:** Replace the plain `CharField` on `Member` with a proper `Department` model so departments are a first-class entity.

**Why needed:**

- The document requires department-wise compliance percentages, color-coded dashboards, and per-department reporting. A `CharField` cannot enforce referential integrity, cannot store metadata (code, head), and makes aggregation fragile (typos cause splits).
- Filtering/grouping by department is a hot path for every compliance query.

**How implemented:**

- New Django model `Department` in `core_system/models.py` with fields: `department_id_PK`, `name`, `code` (short code), `head_officer_id_FK` (nullable FK to `OfficerUser`), `is_active`.
- Add FK `department_id_FK` (nullable) to `Member`, migration to backfill existing data by matching `department` char values.
- Keep old `department` char field as a deprecated fallback (`db_column` alias) or drop after migration.

**Data involved:**

- New table: `DEPARTMENT`
- `Member.department_id_FK` → FK to `Department`
- Existing `Member.department` char data used for backfill.

**Step by step:**

1. Create `Department` model with fields listed above.
2. Run `makemigrations` + `migrate`.
3. Add `department_id_FK` to `Member`, create migration.
4. Write a data migration or management command to: iterate all `Member` records, `get_or_create` a `Department` for each unique `department` string value, assign `department_id_FK`.
5. Update all existing queries that filter on `department__iexact` to use the FK instead.

---

### 1.2 Build compliance service

**Goal:** A centralized service module that computes per-department and overall compliance metrics for **both monthly dues tracking** and **per-member aid contributions**.

**Why needed:**

- The document requires compliance percentages, paid/unpaid/overdue tracking, and dashboard visualizations. The existing code has **two separate payment systems**: (1) monthly dues + membership fees (`MonthlyDues`, `MembershipFee` models), and (2) aid contributions (`Contribution` model). Compliance tracking must cover both.
- Currently there is zero compliance computation — no function answers "what % of members in Dept X paid their dues this month" or "how many members have paid their aid contribution."
- A single service avoids duplicating logic across Treasurer/Auditor/President views.

**How implemented:**

- New file `core_system/services/compliance.py`.
- The service splits into two dimensions:

  **Dimension A — Monthly Dues & Membership Fee Compliance:**
  - `dues_compliance_summary(year, month)` — per department:
    - `total_members` (active, non-retired)
    - `paid_count` (has `MonthlyDues` or `MembershipFee` for period, status >= `Auditor Verified`)
    - `unpaid_count`
    - `overdue_count` (unpaid AND past due date)
    - `percentage` (`paid_count / total_members * 100`)
  - `member_dues_status(member, year, month)` → `"paid"`, `"unpaid"`, `"overdue"`, `"exempt"` (retired)
  - `dues_overdue_bucket(member, year, month)` → `1d`, `3d`, `5d`, `7d`, `15d+`, or `None`

  **Dimension B — Aid Contribution Compliance:**
  - `contribution_compliance_summary(aid_tracking_post_id)` — per department within a specific aid post:
    - `total_members` (non-retired members)
    - `paid_count` (`Contribution.status == "PAID"`)
    - `skipped_count` (`Contribution.status == "SKIPPED"`)
    - `unpaid_count` (`Contribution.status == "NOT_PAID"`)
    - `percentage` (`paid_count / total_members * 100`)
  - `member_contribution_status(member, aid_tracking_post_id)` → `"paid"`, `"unpaid"`, `"skipped"`
  - `all_active_posts_summary()` — returns contribution compliance across all currently active aid posts.

  **Dimension C — Combined Overview:**
  - `overall_department_summary(year, month)` — merges dues + contribution compliance into a unified department score.

**Data involved:**

- `Member` (filtered by `membership_status != 'retired'`)
- `MonthlyDues` (filtered by `month_covered` matching target period)
- `MembershipFee`
- `TransactionVerification` (to check verification status)
- `Contribution` (filtered by `aid_tracking_post_id_FK` and `status`)
- `AidTrackingPost` (to get active aid drives)
- `Department` (for grouping)

**Step by step:**

1. Create `core_system/services/compliance.py`.
2. Implement `dues_compliance_summary(year, month)`:
   - Default to current year/month.
   - Query active departments and their active members.
   - For each department, count members with a MonthlyDues or MembershipFee record (status >= `Auditor Verified`) for the period.
   - Compute percentage, overdue count, bucket.
3. Implement `contribution_compliance_summary(post_id)`:
   - For a given `AidTrackingPost`, group `Contribution` records by member's department.
   - Per department: count PAID, NOT_PAID, SKIPPED. Compute percentage.
4. Implement `member_dues_status()` and `member_contribution_status()` helpers.
5. Implement `overall_department_summary()` that merges both dimensions.
6. Write unit tests for all functions.

---

### 1.3 Compliance API endpoints

**Goal:** REST endpoints that expose compliance data to the frontend dashboards.

**Why needed:**

- All three dashboards need to consume compliance data. Dedicated endpoints keep views clean and allow frontend to refresh independently.
- Role-restricted to ensure only authorized officers can view compliance metrics.

**How implemented:**

- `GET /api/compliance/departments/?year=&month=` → returns the list from `department_compliance_summary()`.
- `GET /api/compliance/department/<dept_id>/members/?year=&month=` → returns per-member breakdown for a single department (member name, status, payment date, overdue bucket).
- Role guard: all three officer roles can access (Treasurer, Auditor, President).

**Data involved:**

- Same as compliance service.

**Step by step:**

1. Create new view file `core_system/compliance_views.py` or add to existing views.
2. Implement `compliance_departments(request)`:
   - Parse `year` and `month` from GET params.
   - Call `department_compliance_summary(year, month)`.
   - Return `JsonResponse`.
3. Implement `compliance_department_members(request, dept_id)`:
   - Fetch all active members of the department.
   - For each, call `member_payment_status()` and `overdue_bucket()`.
   - Return member-level list with status.
4. Register URL patterns in `core_system/urls.py`.
5. Apply `require_role` guard (allow Treasurer, Auditor, President).

---

### 1.4 Overdue tracking

**Goal:** A system that classifies overdue members by day buckets (1d, 3d, 5d, 7d, 15d+) for both **monthly dues** and **aid contributions**, supporting notifications and dashboard display.

**Why needed:**

- The document specifies reminders at days 1, 3, 5, 7, and grace enforcement at 15+. The dashboard needs to show overdue severity, and the notification scheduler needs to target specific buckets.
- Currently there is no overdue calculation anywhere in the codebase for either payment dimension.
- Members can be overdue on monthly dues AND simultaneously unpaid on an active aid contribution — both must be tracked independently.

**How implemented:**

- Extend `compliance.py` with:
  - `dues_overdue_bucket(member, year, month)` — checks monthly dues for the period. Due date = 1st of target month.
  - `contribution_overdue_bucket(member, aid_tracking_post_id)` — checks aid contribution. Due date = post's `target_month` 1st or creation date.
- Buckets: `1` (1 day), `3` (3 days), `5` (5 days), `7` (7 days), `15` (15+ days).
- `GET /api/compliance/overdue-summary/?year=&month=` — returns counts by bucket for dues.
- `GET /api/compliance/contribution-overdue-summary/?post_id=` — returns counts by bucket for a specific aid post.

**Data involved:**

- `Member` (active, non-retired)
- `MonthlyDues` / `MembershipFee` (to check if dues paid)
- `Contribution` (to check if aid contribution paid)
- `AidTrackingPost.target_month` (to compute contribution due date)
- Current date (from `timezone.now()`)

**Step by step:**

1. Add `dues_overdue_bucket(member, year, month)` to compliance service:
   - Get the 1st of `year-month` as due date.
   - If no payment record with status >= `Auditor Verified`, compute `days_overdue = today - due_date`.
   - Return bucket label.
2. Add `contribution_overdue_bucket(member, post_id)`:
   - Get `target_month` from the `AidTrackingPost`.
   - Compute due date (1st of target month, or post creation date if target_month is past).
   - If `Contribution.status != "PAID"`, compute `days_overdue`.
   - Return bucket label.
3. Add `dues_overdue_summary(year, month)` aggregating counts across departments.
4. Add `contribution_overdue_summary(post_id)` aggregating counts across departments for a specific aid post.
5. Expose both as API endpoints.

---

### 1.5 Per-Member Aid Contribution Tracking

**Goal:** A dedicated tracking and compliance view for per-member aid contributions (medical aid/death aid collection drives) — separate from monthly dues tracking.

**Why needed:**

- The document describes an entire aid contribution workflow: "Treasurer records payment → Auditor verifies → President approves → AidTrackingPost created → Contributions collected from all active members." This is a **separate payment system** from monthly dues, with its own `Contribution` model.
- Currently the Auditor and Treasurer dashboards have manual interfaces for marking individual contributions as paid/skipped/notified, but there is no:
  - Compliance percentage per aid post.
  - Department-wise contribution breakdown.
  - Automated reminders for unpaid contributions.
  - Overdue tracking for contributions.
- Without explicit tracking, members can be compliant on monthly dues but delinquent on aid contributions (or vice versa), and the system has no way to report this.

**How implemented:**

- All backend logic lives in `core_system/services/compliance.py` (see Dimension B in 1.2).
- New endpoints:
  - `GET /api/compliance/contributions/posts/` — lists active aid tracking posts with per-department compliance summary.
  - `GET /api/compliance/contributions/post/<post_id>/department/<dept_id>/` — per-member breakdown within a post+department.
- New dashboard sections:
  - **Auditor dashboard:** "Contribution Compliance" tab showing active posts, per-dept percentages, member-level statuses.
  - **President dashboard:** overview of all active aid posts and their collection rates.
- Extend notification system (Phase 5) to send contribution reminders independently from dues reminders.

**Data involved:**

- `AidTrackingPost` (active aid drives)
- `Contribution` (per-member contribution records with `status`, `expected_amount`, `paid_amount`, `payment_date`)
- `Member` (to get department association)
- `Department` (for grouping)

**Step by step:**

1. In `compliance.py`, implement `contribution_compliance_summary(post_id)`:
   - Fetch the `AidTrackingPost`.
   - Group its `Contribution` records by member's department.
   - For each department: count PAID, NOT_PAID, SKIPPED; compute collection percentage; compute total collected vs expected.
   - Return `[{dept_id, dept_name, total_members, paid, unpaid, skipped, percentage, collected_amount, expected_amount}, ...]`.
2. Implement `active_posts_compliance()` — calls above for every active post.
3. Create view `compliance_contribution_posts(request)`:
   - Returns list of active posts with per-department compliance.
4. Create view `compliance_contribution_post_department(request, post_id, dept_id)`:
   - Returns member-level contribution statuses for a specific post+department.
5. Register URLs in `core_system/urls.py`.
6. Frontend: create `static/js/contribution_compliance.js`:
   - Table: post name, target month, departments listed with % and color coding.
   - Drill-down: click department → member list with paid/skipped/unpaid status.
7. Add "Contribution Compliance" panel to Auditor dashboard template.
8. Add a summary card to President dashboard showing active aid posts and their overall collection rates.

---

## Phase 2: Payment Flow & Policy Alignment

---

### 2.1 Clarify deposit-forwarding step

**Goal:** Resolve the mismatch between the document's described flow (Treasurer → President for deposit → Auditor → President for approval) and the current implementation (Treasurer → Auditor → President).

**Why needed:**

- The document says: "Treasurer forwards amount to President (or Vice President) for bank deposit." The current system has no such step.
- This requires stakeholder input to decide whether to add the deposit-forwarding status or confirm the current flow is correct.

**How implemented:**

- Investigation / stakeholder meeting — no code change immediately.
- If confirmed: add a new status `"Forwarded for Deposit"` and optionally a new model `DepositForward` to track the deposit handoff.
- If current flow is correct: update the document to match reality.

**Data involved:**

- Potential: new status in `Status` class, new `DepositForward` table.

**Step by step:**

1. Present the mismatch to stakeholders (President/Treasurer/Auditor).
2. Decide: add deposit step or keep current flow.
3. If adding deposit step:
   - Add `"Forwarded for Deposit"` to `Status` class.
   - Add `"Deposit Confirmed"` status.
   - Add `forwarded_to_id_FK` and `deposit_confirmed_at` fields to `TransactionVerification`.
   - Treasurer view: "forward for deposit" action.
   - President view: "confirm deposit" action.
   - Update compliance service to recognize these statuses.

---

### 2.2 Implement grace-period policy config

**Goal:** Allow the President (or Secretary) to configure grace period days (15–30) via the UI, stored in the database.

**Why needed:**

- The document states: "Grace Period suggested 15-30 days before penalties or account deactivation. Must be defined by President and Treasurer in policy."
- Currently there is no grace period configuration.

**How implemented:**

- New model `PolicyConfig` with key-value pairs, or a simpler approach: add `grace_period_days` to a new `SystemSetting` model.
- Default value: 15 days.
- President dashboard: settings panel to read/write the value.
- Compliance service reads the value for overdue calculations.

**Data involved:**

- New table: `SYSTEM_SETTING` (`setting_key`, `setting_value`, `updated_by`, `updated_at`)

**Step by step:**

1. Create `SystemSetting` model in `core_system/models.py`.
2. Add migration.
3. Pre-populate with default: `grace_period_days = 15`.
4. Create API endpoint `GET/PUT /api/settings/grace-period/` (President-only).
5. Update compliance service to read grace period and flag members beyond it as "Grace Expired".

---

### 2.3 Auto-deactivation cron

**Goal:** A daily background task that deactivates members whose overdue period exceeds the configured grace period.

**Why needed:**

- Document says: ">15 days → Account deactivation if unpaid." This should be automated, not manual.
- Currently no mechanism exists to deactivate members for non-payment.

**How implemented:**

- New management command: `core_system/management/commands/deactivate_overdue_members.py`.
- Queries members who are active, have no payment for the current period, and are past grace period.
- Sets `membership_status = "Deactivated"`, logs in `GlobalAuditTrail`.
- Runs daily via Windows Task Scheduler or a simple cron-loop in `start.ps1`.

**Data involved:**

- `Member.membership_status` → updated to "Deactivated"
- `GlobalAuditTrail` → action "DEACTIVATED"
- `SystemSetting.grace_period_days`

**Step by step:**

1. Create `management/commands/deactivate_overdue_members.py`.
2. Command logic:
   - Get `grace_period_days` from `SystemSetting`.
   - Query active members with no payment for current month.
   - Filter those where `days_overdue > grace_period_days`.
   - For each: update `membership_status = "Deactivated"`, create `GlobalAuditTrail` entry.
3. Schedule to run daily (add to `start.ps1` or Windows Task Scheduler entry).

---

## Phase 3: Dashboard Visualizations

---

### 3.1 Color-coded compliance table

**Goal:** Display department compliance rows with green/yellow/red background colors on all three dashboards.

**Why needed:**

- Document requires "Color-coded cells (e.g., red for overdue, green for current)" and real-time tables showing payment status per department.
- The current dashboards show plain lists — no status visualization.

**How implemented:**

- Frontend: add a new JS module `compliance_table.js` shared across all dashboards.
- Table columns: Department, Total Members, Paid, Unpaid, Overdue, Compliance %.
- Row color: green (≥90%), yellow (≥70%), red (<70%).
- Data source: `GET /api/compliance/departments/`.
- Auto-refresh via WebSocket or periodic polling.

**Data involved:**

- `GET /api/compliance/departments/` response.
- Frontend state (department list, percentages).

**Step by step:**

1. Create `static/js/compliance_table.js`:
   - `fetchComplianceData(year, month)` → calls API.
   - `renderComplianceTable(data, containerId)` → builds HTML table with inline styles for row colors.
   - `getRowColor(percentage)` → returns `#d4edda` (green), `#fff3cd` (yellow), `#f8d7da` (red).
2. Include `compliance_table.js` in each dashboard template.
3. Add a `<div id="compliance-table-container">` in each dashboard.
4. Wire WebSocket refresh to re-fetch data on changes.

---

### 3.2 Heatmap

**Goal:** A grid of departments (rows) × months (columns) with red/yellow/green cells to visually identify problem areas.

**Why needed:**

- Document explicitly requires: "Heatmap to highlight high-risk (red) vs. low-risk (green) departments."
- Heatmap is a core requirement for the Auditor dashboard.

**How implemented:**

- Backend: `GET /api/compliance/heatmap?year=2026` → returns a 2D array: `{departments: [...], months: [...], cells: [[dept_idx, month_idx, percentage, color], ...]}`.
- Frontend: render as an HTML `<table>` with colored cells. Each cell is a `<td>` with `background-color` set. Clicking a cell drills into `department/<id>/members/`.
- Use the same color thresholds as compliance table.

**Data involved:**

- `department_compliance_summary()` called for each month (Jan–Dec).
- Response shape: `{departments: [dept names], months: ['2026-01', ...], cells: [[row, col, pct, color], ...]}`.

**Step by step:**

1. Backend: add `heatmap_data(year)` to `compliance.py`:
   - For each month Jan–Dec, call `department_compliance_summary(year, month)`.
   - Build a matrix of `[dept_name][month_str] = percentage`.
   - Assign color per cell using same thresholds.
   - Return structured JSON.
2. Backend: add view `compliance_heatmap(request)` using `@require_GET`.
3. Frontend: create `static/js/heatmap.js`:
   - `fetchHeatmapData(year)` → calls API.
   - `renderHeatmap(data, containerId)` → builds table with row headers (departments), column headers (months), colored cells.
   - Add click handler on cells → navigate to department detail view.
4. Include in Auditor and President dashboards.

---

### 3.3 Bar chart — contributions per department

**Goal:** A bar chart comparing total monetary contributions collected from each department.

**Why needed:**

- Document requires bar charts to "compare total contributions across departments."
- Helps Treasurer and President see which departments are contributing the most/least.

**How implemented:**

- Backend: `GET /api/compliance/contributions-by-department?year=&month=`.
- Frontend: render using Chart.js (already available? Check if Chart.js is in the project — if not, add via CDN or npm).
- If Chart.js is not available, render using inline SVG or a simple CSS bar chart.

**Data involved:**

- `MonthlyDues.amount` (sum per department, filtered by status >= `Auditor Verified`)
- `MembershipFee.amount` (same)

**Step by step:**

1. Backend: add `contributions_by_department(year, month)` to compliance service:
   - Sum `MonthlyDues.amount` grouped by `member_id_FK__department_id_FK`.
   - Sum `MembershipFee.amount` same way.
   - Combine totals per department.
   - Return `[{dept_name, total_amount}, ...]`.
2. Frontend: create `static/js/bar_chart.js`:
   - Use Chart.js if available; otherwise render CSS bars.
   - Render chart in designated container.
3. Add to Treasurer and President dashboards.

---

### 3.4 Line graph — monthly payment trend

**Goal:** A line graph showing overall payment percentage across fiscal year months.

**Why needed:**

- Document requires "Line Graph: Track payment percentages over fiscal months."
- Essential for the President dashboard to see compliance trends over time.

**How implemented:**

- Backend: `GET /api/compliance/monthly-trend?year=2026` → returns percentages for Jan–Dec.
- Frontend: Chart.js line chart.
- Can reuse the same `GET /api/compliance/heatmap` data and extract overall per-month percentages.

**Data involved:**

- Same compliance data, aggregated per month (all departments combined).

**Step by step:**

1. Backend: add `monthly_trend(year)` to compliance service:
   - For each month, compute overall `paid / total * 100` across all departments.
   - Return `[{month: '2026-01', percentage: 85.0}, ...]`.
2. Frontend: create `static/js/line_chart.js`:
   - Chart.js line graph.
   - X-axis: months, Y-axis: %.
3. Add to President dashboard.

---

### 3.5 Pie chart — paid vs unpaid vs overdue

**Goal:** Pie charts showing the proportion of paid, unpaid, and overdue members for **both** monthly dues and aid contributions.

**Why needed:**

- Document requires "Pie Chart: Show proportion of paid vs. unpaid members."
- Quick visual snapshot for all dashboards.
- Two separate pie charts are needed: one for dues compliance, one for aid contribution compliance — a member can be paid on dues but unpaid on contributions.

**How implemented:**

- **Pie Chart A (Dues):** Backend aggregates `dues_compliance_summary()` across all departments. Slices: Paid (green), Unpaid (yellow), Overdue (red).
- **Pie Chart B (Contributions):** Backend aggregates `contribution_compliance_summary()` across active aid posts. Slices: Paid (green), Unpaid (yellow), Skipped (gray).
- Frontend: Chart.js or pure CSS. Two pie charts displayed side by side or toggled via tab.

**Data involved:**

- `dues_compliance_summary()` and `contribution_compliance_summary()` aggregated totals.

**Step by step:**

1. Backend: add endpoint `GET /api/compliance/pie-data/?year=&month=` returning:
   - `dues: {paid, unpaid, overdue}`
   - `contributions: {paid, unpaid, skipped}`
2. Frontend: create `static/js/pie_chart.js`:
   - Chart.js pie chart.
   - Tab/switch to toggle between dues and contribution views.
   - `labels: ['Paid', 'Unpaid', 'Overdue']`, `data: [total_paid, total_unpaid, total_overdue]`.
3. Add to all three dashboards with a label showing which dimension is displayed.

---

## Phase 4: Reporting (Excel Export)

---

### 4.1 Add `openpyxl` dependency

**Goal:** Install the library used to generate `.xlsx` Excel files.

**Why needed:**

- Excel export is explicitly required: "Exportable Excel sheets for overall and per-department summaries."
- Django has no built-in Excel support.

**How implemented:**

- Add `openpyxl` to `requirements.txt`, run `pip install`.

**Step by step:**

1. Add `openpyxl` to `requirements.txt`.
2. Run `pip install -r requirements.txt`.

---

### 4.2 Overall report endpoint

**Goal:** Downloadable `.xlsx` with an overall summary and per-department sheets.

**Why needed:**

- Document requires exportable Excel sheets for overall summaries.
- Treasurer, Auditor, and President all need to generate reports.

**How implemented:**

- `GET /api/reports/overall/?year=&month=` returns a file response with `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- Sheet 1: **Summary** — total members, paid, unpaid, overdue, overall percentage.
- Sheet 2+: **Per Department** — one sheet per dept with member-level detail (name, employee ID, amount paid, payment date, status).

**Data involved:**

- Compliance service data (both dues + contributions).
- Member-level payment records and contribution records.

**Step by step:**

1. Create `core_system/services/reporting.py`:
   - `generate_overall_report(year, month)` → creates `openpyxl.Workbook`.
   - **Sheet 1: Summary** — totals, compliance %, paid/unpaid/overdue counts, active aid posts, collection rates.
   - **Sheet 2: Dues by Department** — per-dept dues compliance table.
   - **Sheet 3: Contributions by Department** — per-dept contribution compliance for each active aid post.
   - **Per-department sheets** — for each dept: member-level detail (name, employee ID, dues status, contribution status, amounts).
   - Return the workbook.
2. Create view `download_overall_report(request)`:
   - Parse `year` and `month`, call service, return `HttpResponse` with workbook as attachment.
3. Register URL: `GET /api/reports/overall/`.

---

### 4.3 Per-department report endpoint

**Goal:** Downloadable `.xlsx` for a single department, including both monthly dues and contribution compliance.

**Why needed:**

- Document requires per-department summaries.
- Auditor needs to generate focused reports for specific departments.
- A single-department report must show both payment dimensions side by side.

**How implemented:**

- `GET /api/reports/department/<dept_id>/?year=&month=&post_id=all` returns single-department `.xlsx`.
- **Sheet 1: Dues Compliance** — member-level monthly dues status.
- **Sheet 2: Contribution Compliance** — member-level contribution status across active aid posts.
- **Sheet 3: Combined** — each member's overall standing (dues + contributions).

**Data involved:**

- Members of the department + dues payment records + contribution records.

**Step by step:**

1. Add `generate_department_report(dept_id, year, month)` to `reporting.py`:
   - Fetch all active members of the department.
   - For each member: dues status, contribution status per active post.
   - Write to three sheets.
2. Create view `download_department_report(request, dept_id)`.
3. Register URL: `GET /api/reports/department/<dept_id>/`.

---

### 4.4 Contribution-specific report endpoint

**Goal:** Downloadable `.xlsx` focused solely on aid contribution compliance for a specific post or across all active posts.

**Why needed:**

- Auditor and President need to see contribution collection performance independently from dues compliance.
- Aid tracking posts have their own lifecycle and stakeholders.

**How implemented:**

- `GET /api/reports/contributions/?post_id=` (optional, all active posts if omitted) returns `.xlsx`.
- **Per-post sheet:** summary (total expected, collected, collection rate %) + per-department breakdown + per-member detail.

**Data involved:**

- `AidTrackingPost`, `Contribution`, `Member`, `Department`.

**Step by step:**

1. Add `generate_contribution_report(post_id=None)` to `reporting.py`.
2. If `post_id` is given: single sheet with post detail + department + member breakdown.
3. If omitted: one summary sheet + one sheet per active post.
4. Create view and register URL.

---

### 4.4 President "Generate Report" button

**Goal:** UI button on President dashboard that triggers the Excel download.

**Why needed:**

- President should be able to generate and download reports with one click.

**How implemented:**

- Add a "Generate Report" dropdown/button in the President dashboard.
- Options: "Overall Report (Excel)", "Department Report (Excel)" — prompts for year/month/department.
- Uses the existing API endpoints.

**Step by step:**

1. Add button HTML to `president_dashboard.html`.
2. Wire via JS: `window.location.href = '/api/reports/overall/?year=' + year + '&month=' + month`.

---

## Phase 5: Notification Scheduling

---

### 5.1 Scheduled notification model

**Goal:** A database table to track scheduled notifications and their delivery status. Must support **two independent reminder tracks**: monthly dues reminders AND aid contribution reminders.

**Why needed:**

- The document specifies configurable alerts at days 1, 3, 5, 7 via SMS or email. A persistent model is needed to track what was sent, to whom, and when.
- Since members can be overdue on **monthly dues** independently from being unpaid on **aid contributions**, the notification system must track which dimension a reminder is for. A member might need a dues reminder but already paid their contribution (or vice versa).

**How implemented:**

- Add a `category` field to `Notification` model: `"dues"`, `"contribution"`, or `"general"`.
- Add fields: `scheduled_date`, `channel` (email/sms/push), `error_message`.
- Alternatively, create `ScheduledNotification` model with:
  - `scheduled_notification_id_PK`
  - `member_id_FK` (FK to `Member`)
  - `category` (`"dues"` or `"contribution"`)
  - `related_post_id` (nullable FK to `AidTrackingPost` — only for contribution reminders)
  - `overdue_bucket` (`1d`, `3d`, `5d`, `7d`, `15d+`)
  - `notification_type` (reminder, final_notice, deactivation_warning)
  - `channel` (email, sms)
  - `scheduled_date`
  - `sent_at` (null until sent)
  - `delivery_status` (pending, sent, failed)
  - `error_message` (null if successful)

**Data involved:**

- Extended `NOTIFICATION` table or new `SCHEDULED_NOTIFICATION` table.

**Step by step:**

1. Assess existing `Notification` model — decide: extend it or create a separate `ScheduledNotification` model.
2. If extending: add `category`, `scheduled_date`, `channel`, `error_message` fields.
3. If new model: create `ScheduledNotification` with fields listed above.
4. Run `makemigrations` + `migrate`.
5. Update `services/notifications.py` to support both categories.

---

### 5.2 Reminder cron task (Dues + Contributions)

**Goal:** A daily management command that sends notifications for **both** overdue monthly dues and unpaid aid contributions, based on each member's overdue bucket.

**Why needed:**

- The document requires automated reminders at days 1, 3, 5, 7. Manual sending is impractical.
- Currently there is no automated notification system.
- Members can be compliant on dues but delinquent on contributions (or vice versa). The cron must check both dimensions independently and send separate notifications per category.

**How implemented:**

- New management command: `core_system/management/commands/send_payment_reminders.py`.
- The command runs **two independent passes**:

  **Pass A — Monthly Dues Reminders:**
  1. Query all active, non-retired members without a `MonthlyDues`/`MembershipFee` record for the current period (status >= `Auditor Verified`).
  2. Compute each member's `dues_overdue_bucket()` from compliance service.
  3. Check if a dues-reminder notification was already sent for this bucket today (deduplicate by `member_id + category='dues' + bucket`).
  4. If not sent, generate message from template and send.
  5. Record in `Notification` table with `category='dues'`.

  **Pass B — Aid Contribution Reminders:**
  1. Query all active `AidTrackingPost` records.
  2. For each post, find members with `Contribution.status == "NOT_PAID"`.
  3. Compute each member's `contribution_overdue_bucket()` from compliance service.
  4. Check if a contribution-reminder notification was already sent for this post+bucket today (deduplicate by `member_id + category='contribution' + related_post_id + bucket`).
  5. If not sent, generate message from template (e.g., "Your aid contribution for {member_name}'s medical aid is due.") and send.
  6. Record in `Notification` table with `category='contribution'` and `related_post_id`.

**Data involved:**

- `Member`, `MonthlyDues`, `MembershipFee`, `TransactionVerification` (Pass A)
- `AidTrackingPost`, `Contribution` (Pass B)
- `Notification` (both passes)

**Step by step:**

1. Create `management/commands/send_payment_reminders.py`.
2. Implement Pass A (dues):
   - Query overdue members for current month.
   - Compute `dues_overdue_bucket()`.
   - Deduplicate against existing `Notification` records.
   - Send via `queue_and_send_member_notification()`.
3. Implement Pass B (contributions):
   - Loop active aid posts.
   - For each post, query NOT_PAID contributions.
   - Compute `contribution_overdue_bucket()`.
   - Deduplicate.
   - Send with contribution-specific message template.
4. Log all sends with timestamps.
5. Schedule to run daily (via Windows Task Scheduler or `start.ps1`).

---

### 5.3 SMS integration

**Goal:** Add SMS as a notification channel alongside email.

**Why needed:**

- Document specifies SMS as "preferred for immediate alerts; higher cost, requires monthly subscription."
- Currently only email is implemented.

**How implemented:**

- Add configuration for an SMS gateway (e.g., Twilio, Semaphore, or local SMS API).
- New service function `send_sms(recipient_number, message)`.
- Extend `Notification` model to support SMS channel.
- Update the reminder cron to send SMS for urgent buckets (5d, 7d, 15d).

**Data involved:**

- SMS gateway credentials (in `.env`).
- `Member.contact_number` (SMS recipient).
- `Notification` table.

**Step by step:**

1. Add SMS gateway config to `settings.py` (from `.env`).
2. Add `send_sms(recipient_number, message)` to `services/notifications.py`.
3. Update the reminder cron: for buckets >= 5d, send SMS instead of (or in addition to) email.
4. Test with a sandbox/development SMS account.

---

### 5.4 Configurable schedule UI

**Goal:** Allow President/Secretary to configure reminder intervals, channel preferences, and message templates.

**Why needed:**

- Document requires "Configurable alerts (1-day, 3-day, 5-day, 7-day) via SMS or email."
- "All system features should be configurable by the President/Secretary."

**How implemented:**

- Store notification settings in `SystemSetting` table:
  - `reminder_intervals` (JSON: `[1, 3, 5, 7, 15]`)
  - `reminder_channels` (JSON: `{"1": "email", "3": "email", "5": "sms", "7": "sms", "15": "email+sms"}`)
  - `reminder_message_templates` (JSON: `{"1": "Dear {name}, your payment is due...", ...}`)
- President dashboard: settings panel with form fields.

**Data involved:**

- `SystemSetting` table.
- Frontend form state.

**Step by step:**

1. Add settings keys to `SystemSetting` (or create dedicated `NotificationConfig` model).
2. Create API endpoints:
   - `GET /api/settings/notifications/` — returns current config.
   - `PUT /api/settings/notifications/` — updates config (President-only).
3. President dashboard: add "Notification Settings" panel with:
   - Interval checkboxes (day 1, 3, 5, 7, 15).
   - Channel radio/select per interval.
   - Message template text areas (with `{name}`, `{amount}`, `{due_date}` placeholders).
4. Update reminder cron to read config instead of hardcoded values.

---

### 5.5 Grace-period notifications

**Goal:** Send final notices and deactivation warnings when members approach or exceed the grace period.

**Why needed:**

- Document says: "Day 7 – final notice before grace period expires" and "15-30 days grace period before penalties or account deactivation."
- Members should be warned before deactivation.

**How implemented:**

- Extend the reminder cron to handle the 7-day (final notice) and 15-day (deactivation warning) buckets.
- Message templates for these scenarios:
  - 7-day: "This is your final notice. Your account will be suspended in 8 days if unpaid."
  - 15-day: "Your account has been deactivated due to non-payment. Please contact the Treasurer."

**Data involved:**

- Same as reminder cron.

**Step by step:**

1. Add message templates for `final_notice` (day 7) and `deactivation_warning` (day 15).
2. Update the reminder cron to use these templates at the appropriate buckets.
3. Ensure the auto-deactivation cron (`deactivate_overdue_members.py`) runs after these notifications are sent.

---

## Phase 6: Auditor Workflow Enhancements

---

### 6.1 Formal "Auditor Report" generation

**Goal:** Allow the Auditor to generate a formal compliance report from the system data, which is then submitted to the President.

**Why needed:**

- Document requires: "Generate report for President and Secretary."
- The `AuditFindingsReport` model already exists but has no endpoints for creating or viewing reports.

**How implemented:**

- Backend: `POST /api/auditor/reports/create/` — reads compliance data for a given period, creates an `AuditFindingsReport` record with auto-generated summary.
- Backend: `GET /api/auditor/reports/` — list reports.
- Backend: `GET /api/auditor/reports/<id>/` — report detail (JSON).
- The report summary includes: period covered, total members, paid %, unpaid %, overdue %, department breakdown, notable issues.

**Data involved:**

- `AuditFindingsReport` model.
- Compliance service data.

**Step by step:**

1. Add `create_auditor_report(year, month, officer)` to `services/reporting.py`:
   - Gathers compliance data for the period.
   - Creates `AuditFindingsReport` with auto-generated summary.
   - Returns the report object.
2. Create view `auditor_create_report(request)`:
   - Parse `year` and `month`.
   - Call service, return report detail.
3. Add list/detail endpoints for viewing past reports.
4. Register URL patterns under `/api/auditor/reports/`.

---

### 6.2 Bank deposit verification

**Goal:** Add deposit reference matching to the auditor's verification workflow.

**Why needed:**

- Document says: "Verify each entry against bank deposit records."
- Currently the auditor verifies payments without any deposit/bank reconciliation.

**How implemented:**

- Add optional `deposit_slip_reference` field to `TransactionVerification`.
- Auditor UI: during verification, enter the bank deposit slip reference number.
- Future: allow upload of bank statement CSV for automated matching.
- For now: manual entry of deposit reference.

**Data involved:**

- `TransactionVerification` (add `deposit_slip_reference` field).

**Step by step:**

1. Add `deposit_slip_reference` field to `TransactionVerification` model.
2. Migration.
3. Update `auditor_verify_payment` view to accept and store the deposit reference.
4. Update Auditor dashboard UI: add "Deposit Slip Ref" field to the verification form.

---

### 6.3 Archive verified data per term

**Goal:** Archival process that packages audit data at the end of a fiscal year/term for the next auditor.

**Why needed:**

- Document requires: "Archive verified data for next term's auditor."
- Current archiving only happens per-transaction when President approves. A term-end bulk archive is needed.

**How implemented:**

- Management command or API: `POST /api/auditor/archive-term/`:
  - Collects all approved transactions for the fiscal year.
  - Creates summary archive records.
  - Marks old data as read-only.
- New model or extend existing `TransactionArchive` with a `term` field.

**Data involved:**

- `TransactionArchive`
- `TransactionVerification`
- `GlobalAuditTrail`

**Step by step:**

1. Add `fiscal_term` field to `TransactionArchive` (e.g., "2024-2025").
2. Create `archive_fiscal_term(term, officer)` service:
   - Query all approved/released transactions for the term.
   - Bulk-create archive records if not already archived.
   - Log in `GlobalAuditTrail`.
3. Create view + URL endpoint.
4. Add "Archive Term" button to Auditor dashboard (with confirmation dialog).

---

## Phase 7: President Monitoring Dashboard

---

### 7.1 Full compliance overview

**Goal:** A comprehensive overview page on the President dashboard showing KPI cards: total members, paid %, overdue %, department rankings.

**Why needed:**

- Document says: "President – monitors all membership payments; final authority on fund allocation."
- Current KPI endpoint returns only counts of pending items. A full compliance overview is needed.

**How implemented:**

- Extend `president_kpi_counts` to include:
  - `total_active_members`
  - `overall_compliance_percentage`
  - `total_paid`
  - `total_unpaid`
  - `total_overdue`
  - `departments_below_threshold` (list of departments with compliance < 70%)
  - `top_performing_departments` (top 3)
  - `bottom_performing_departments` (bottom 3)
- Frontend: KPI cards at the top of the President dashboard.

**Data involved:**

- Compliance service data.

**Step by step:**

1. Update `president_kpi_counts` view to include compliance stats.
2. Add HTML cards to `president_dashboard.html`:
   - Total Members, Compliance %, Paid, Unpaid, Overdue counts.
   - Top/Bottom departments list.
3. Wire JS to fetch and render on dashboard load.

---

### 7.2 Auditor report approval flow

**Goal:** President can view, comment on, and sign off on the Auditor's final report.

**Why needed:**

- Document: "President reviews auditor's report and approves any further action."
- Currently there is no formal report review workflow.

**How implemented:**

- New endpoint: `GET /api/president/auditor-reports/` — lists all `AuditFindingsReport` records with status `"Submitted"`.
- New endpoint: `POST /api/president/auditor-reports/<id>/approve/` — President signs off.
- New endpoint: `POST /api/president/auditor-reports/<id>/request-revision/` — sends back to Auditor with comments.
- Status flow: `Draft` (Auditor) → `Submitted` → `Approved` or `Revision Requested`.

**Data involved:**

- `AuditFindingsReport` model (already has `presentation_status`, `certification_status`).

**Step by step:**

1. Add `approve_auditor_report(report_id, officer, remarks)` to `services/reporting.py`.
2. Add `request_report_revision(report_id, officer, remarks)`.
3. Create views + URL endpoints.
4. Add "Auditor Reports" section to President dashboard with list, detail, and approve/revision buttons.

---

### 7.3 Fund allocation dashboard

**Goal:** President dashboard section showing total funds collected (membership fees + monthly dues) vs disbursed (aid claims released), with a visual breakdown.

**Why needed:**

- Document: President has "Full view & edit of finances" and "final authority on fund allocation."
- Current `cash_flow_summary` endpoint exists but is not integrated into the President dashboard.

**How implemented:**

- Reuse and extend `cash_flow_summary` endpoint from `treasurer_views.py` (make it accessible to President).
- Frontend: cards showing:
  - Total funds collected (YTD)
  - Total funds disbursed (YTD)
  - Current balance
  - Breakdown: membership fees, monthly dues, medical aid, death aid
- Optional: bar chart comparing income vs expenses by month.

**Data involved:**

- `TransactionArchive` (approved/finalized transactions).
- `MembershipFee`, `MonthlyDues` (for income).
- `MedicalAid`, `DeathAid` (for disbursement).

**Step by step:**

1. Extend `cash_flow_summary` to accept a `role` parameter or create `president_cash_flow_summary`.
2. Add income and expense breakdown by category.
3. Frontend: add "Financial Overview" section to President dashboard with cards and chart.
4. Wire real-time updates via WebSocket.

---

## Summary Table

| Phase | Area                 | Key Deliverable                                                                                                                                    |
| ----- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | Compliance Engine    | `Department` model; compliance service covering **dues + contributions**; API; overdue tracking for both dimensions; per-member contribution tracking |
| 2     | Payment Flow         | Deposit-forwarding clarification, grace period config, auto-deactivation                                                                           |
| 3     | Visualizations       | Color-coded table, heatmap, bar chart, line graph, **dual pie charts (dues + contributions)**                                                      |
| 4     | Reporting            | Excel export (overall + per-department + **contribution-specific**), President "Generate" button                                                   |
| 5     | Notifications        | Scheduled reminders **for both dues + contributions**, SMS channel, configurable schedule UI, grace-period notices                                  |
| 6     | Auditor Enhancements | Formal report generation, bank deposit verification, term-end archiving, contribution compliance views                                              |
| 7     | President Dashboard  | Compliance overview, report approval flow, fund allocation dashboard, active aid post collection rates                                              |
