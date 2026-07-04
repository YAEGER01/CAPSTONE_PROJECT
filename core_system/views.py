# =========================================================================
# MIGRATION STATUS — All views moved to dedicated files:
#   - President views   → president_views.py  (10 views)
#   - Treasurer views   → treasurer_views.py  (19 views)
#   - Auditor views     → auditor_views.py    (10 views + 4 helpers)
# This file now only re-exports logout_view.
# =========================================================================
from core_system.logout_view import logout_view

logout_view = logout_view
