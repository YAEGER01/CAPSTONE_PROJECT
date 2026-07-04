# Data Consistency Background Validator

## Goal
A lightweight, standalone background process that continuously validates database consistency across related tables (DeathAid, MedicalAid, AidTrackingPost, TransactionVerification, GlobalAuditTrail) and pushes real-time alerts via WebSocket when discrepancies are found. Runs as a separate OS process with zero impact on web server performance.

## Description
- Management command `validate_consistency` runs as a standalone daemon (`python manage.py validate_consistency --loop --ws-notify`)
- Every 60 seconds, runs 4 modular checks using lightweight SQL aggregate queries
- Detected discrepancies are logged to a new `DataIntegrityLog` table with dedup (same issue is bumped, not duplicated)
- Optionally broadcasts `integrity_alert` WebSocket messages to the affected dashboard in real time
- Frontend shows a non-blocking toast when an alert arrives — no page refresh needed

---

## Implementation Steps

### Step 1 — Model: DataIntegrityLog
- **File:** `core_system/models.py`
- Add `DataIntegrityLog` model with fields:
  - `id` (BigAutoField, PK)
  - `check_name` (CharField 100) — e.g. `"post_claim_status_mismatch"`
  - `severity` (CharField 20) — choices: `info`, `warning`, `error`
  - `table_name` (CharField 50) — affected table name
  - `record_id` (IntegerField, null, blank) — specific record if applicable
  - `expected_value` (TextField, null, blank)
  - `actual_value` (TextField, null, blank)
  - `details` (JSONField, null, blank) — extra context
  - `resolved` (BooleanField, default=False)
  - `created_at` (DateTimeField, auto_now_add)
  - `last_seen_at` (DateTimeField, auto_now) — bumped on re-detection
  - `resolved_at` (DateTimeField, null, blank)
- Meta: ordering = `-created_at`, verbose_name_plural = "Data integrity logs"
- **Run:** `python manage.py makemigrations` + `python manage.py migrate`

### Step 2 — Management Command: validate_consistency
- **File:** `core_system/management/commands/validate_consistency.py`
- Extends `BaseCommand`
- Uses `argparse` for:
  - `--loop` (store_true) — run continuously
  - `--interval` (int, default=60) — seconds between cycles
  - `--ws-notify` (store_true) — enable WebSocket broadcast
  - `--severity` (str, default="warning") — minimum severity to log
- **Core loop:**
  ```python
  def handle(self, *args, **options):
      while True:
          self.run_all_checks(options)
          if not options["loop"]:
              break
          time.sleep(options["interval"])
  ```
- **4 check functions (each wrapped in try/except):**

  1. `check_post_claim_status()`
     - Query `AidTrackingPost` with `is_active=False`, select_related `archive_id_FK`
     - For each: if `archive.transaction_type in ("death_aid", "medical_aid")`, look up original record via MODEL_MAP
     - If `record.status != "Released"` → log warning
     - SQL profile: 2 queries, no full table scan (indexed fields)

  2. `check_orphaned_verifications()`
     - `TransactionVerification.objects.filter(table_name="death_aid")` — collect record_ids
     - Find which record_ids have no matching `DeathAid` row
     - Same for `medical_aid` → `MedicalAid`
     - SQL profile: 2-3 queries with `VALUES` / `__in`

  3. `check_count_mismatches()`
     - Compare `DeathAid.objects.filter(status="Approved", president_decided__isnull=False).count()` vs `AidTrackingPost.objects.filter(aid_type="death_aid", is_active=True).count()`
     - Compare `DeathAid.objects.filter(status="Released").count()` vs `AidTrackingPost.objects.filter(aid_type="death_aid", is_active=False).count()`
     - Same for `medical_aid`
     - SQL profile: 4 `SELECT COUNT` queries

  4. `check_audit_trail_vs_state()`
     - `GlobalAuditTrail.objects.filter(action="RELEASED", table_name="death_aid")` — verify `DeathAid.status == "Released"`
     - `GlobalAuditTrail.objects.filter(action="APPROVED", table_name="death_aid")` — verify `DeathAid.president_decision == "Approved"`
     - Same for `medical_aid`
     - SQL profile: bounded queries with `LIMIT`

- **Dedup logic** (in a helper `_log_or_bump(check_name, severity, table_name, record_id, expected, actual, details)`):
  - Check for existing unresolved `DataIntegrityLog` matching `(check_name, table_name, record_id)`
  - If found → update `last_seen_at` (no new row)
  - If not found → create new row
  - If issue no longer exists → mark existing rows `resolved=True, resolved_at=now`
- **WebSocket broadcast** (if `--ws-notify`):
  - After logging, call `_broadcast_to_group("treasurer_dashboard", {"type": "integrity_alert", "alerts": [...]})`
  - For president dashboard items: `"president_dashboard"`
  - For auditor dashboard items: `"auditor_dashboard"`

### Step 3 — WebSocket Consumers: integrity_alert handler
- **File:** `core_system/consumers.py`
- Add handler to **TreasurerDashboardConsumer** (after `data_changed` / line ~217):
  ```python
  async def integrity_alert(self, event):
      await self.send(text_data=json.dumps({
          "type": "integrity_alert",
          "alerts": event.get("alerts", []),
      }))
  ```
- Add same handler to **PresidentDashboardConsumer** (after `notification_summary`)
- Add same handler to **AuditorDashboardConsumer** (same pattern)

### Step 4 — API Endpoint: /api/validate/integrity-logs/
- **File:** `core_system/treasurer_views.py` (or new `core_system/validation_views.py`)
- `@require_GET` view:
  - Guard: `require_role(request, role=...)` — accessible to Treasurer, President, Auditor
  - Query params: `severity`, `resolved`, `check_name`, `limit` (default 50), `offset`
  - Returns paginated JSON `{"ok": true, "logs": [...], "total": N}`
- Register URL in `core_system/urls.py`: `path("api/validate/integrity-logs/", views.integrity_logs_list)`

### Step 5 — Frontend WebSocket handler
- **File:** `static/js/Treasurer/websocket.js`
  - In `onmessage` switch/add `case "integrity_alert":`
  - Show toast: `` `⚠️ Data inconsistency: ${alert.check_name}` ``
  - Optionally log to console for debugging
- **File:** `static/js/President/websocket.js`
  - Same handler
- **File:** `static/js/Auditor/websocket.js` or `static/js/Auditor/notification_listener.js`
  - Same handler

### Step 6 — Verification
- [ ] Run `python manage.py validate_consistency` (single pass) — verify logs are created
- [ ] Run `python manage.py validate_consistency --loop --interval 10` — verify continuous mode
- [ ] Force a mismatch (e.g. manually set DeathAid.status back to "Approved" after post is finished) — verify `integrity_alert` WebSocket message reaches the dashboard
- [ ] Verify no duplicate rows for the same issue (dedup works)
- [ ] Verify resolved issues are auto-cleared when the data is fixed
