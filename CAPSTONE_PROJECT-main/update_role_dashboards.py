from pathlib import Path
import re

base = Path('Document_Archiving_System/Secretary/templates/website/dashboard.html').read_text(encoding='utf-8')

roles = {
    'QR_Attendance_System/PIO': {
        'label': 'PIO',
        'subtitle': "Manage QR attendance, event scanning, and attendance reports in one view.",
        'modules': '''    <!-- Modules Section -->
      <div class="sidebar-section">
        <h3 class="sidebar-section-title">ATTENDANCE</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item active">
            <i class="fas fa-qrcode"></i>
            <span>QR DASHBOARD</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="attendance-qr">
            <i class="fas fa-qrcode"></i>
            <span>Generate QR Codes</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="attendance-monitor">
            <i class="fas fa-chart-line"></i>
            <span>Monitor Attendance</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="attendance-events">
            <i class="fas fa-calendar-days"></i>
            <span>Event Management</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="attendance-export">
            <i class="fas fa-file-export"></i>
            <span>Export Logs</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h3 class="sidebar-section-title">REPORTS</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item">
            <i class="fas fa-chart-pie"></i>
            <span>Scan Summary</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-users"></i>
            <span>Attendance Rate</span>
          </a>
        </nav>
      </div>''',
        'cards': '''      <!-- Overview Cards -->
      <div class="overview-cards">
        <article class="info-card">
          <div class="card-icon attendance">
            <i class="fas fa-calendar-check"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Active events</span>
            <strong>{{ dashboard.active_events }}</strong>
            <p class="card-meta">Live this week</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon members">
            <i class="fas fa-user-check"></i>
          </div>
          <div class="card-content">
            <span class="card-label">QR codes generated</span>
            <strong>{{ dashboard.qr_codes }}</strong>
            <p class="card-meta">Since last update</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon treasury">
            <i class="fas fa-chart-line"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Average scan rate</span>
            <strong>{{ dashboard.scan_rate }}%</strong>
            <p class="card-meta">Across active events</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon approvals">
            <i class="fas fa-user-check"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Attendees today</span>
            <strong>{{ dashboard.attendees_today }}</strong>
            <p class="card-meta">Checked in so far</p>
          </div>
        </article>
      </div>''',
        'main': '''      <!-- Main Panels -->
      <div class="main-panels">
        <section class="panel module-status">
          <div class="panel-heading">
            <h2>Event queue</h2>
            <a href="#">View all</a>
          </div>
          <div class="panel-list">
            {% for item in dashboard.event_status %}
            <article class="panel-item">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.subtitle }}</p>
              </div>
              <span class="status-pill {{ item.status|lower }}">{{ item.status }}</span>
            </article>
            {% endfor %}
          </div>
        </section>

        <section class="panel attendance-chart">
          <div class="panel-heading">
            <h2>Attendance overview</h2>
            <a href="#">Full report</a>
          </div>
          <div class="attendance-list">
            {% for event in dashboard.attendance_events %}
            <div class="attendance-row">
              <span>{{ event.label }}</span>
              <div class="attendance-bar-wrap">
                <div class="attendance-bar" style="--fill: {{ event.value }}%;"></div>
              </div>
              <strong>{{ event.value }}%</strong>
            </div>
            {% endfor %}
          </div>
        </section>
      </div>''',
        'lower': '''      <!-- Lower Panels -->
      <div class="lower-panels">
        <section class="panel approvals-list">
          <div class="panel-heading">
            <h2>Recent scan logs</h2>
            <span class="items-count">{{ dashboard.scan_logs|length }} entries</span>
          </div>
          <div class="panel-list">
            {% for log in dashboard.scan_logs %}
            <article class="panel-item approval-item">
              <div>
                <strong>{{ log.event }}</strong>
                <p>{{ log.detail }}</p>
              </div>
              <div class="approval-actions">
                <button class="btn-icon-action btn-approve" title="View"><i class="fas fa-eye"></i></button>
              </div>
            </article>
            {% endfor %}
          </div>
        </section>
      </div>''',
    },
    'Profiling_System/BUSINESS_MANAGER': {
        'label': 'Business Manager',
        'subtitle': "Review member profiles, verify submissions, and manage profiling reports.",
        'modules': '''    <!-- Modules Section -->
      <div class="sidebar-section">
        <h3 class="sidebar-section-title">PROFILING</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item active">
            <i class="fas fa-id-card"></i>
            <span>PROFILE DASHBOARD</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="members-profiles">
            <i class="fas fa-user"></i>
            <span>Member Profiles</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="members-status">
            <i class="fas fa-list-check"></i>
            <span>Profile Verification</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="members-history">
            <i class="fas fa-clock"></i>
            <span>Update History</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h3 class="sidebar-section-title">MEMBERSHIP</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item feature-launcher" data-modal-key="members-add">
            <i class="fas fa-user-plus"></i>
            <span>Add Profiles</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-users"></i>
            <span>Membership Growth</span>
          </a>
        </nav>
      </div>''',
        'cards': '''      <!-- Overview Cards -->
      <div class="overview-cards">
        <article class="info-card">
          <div class="card-icon members">
            <i class="fas fa-id-badge"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Total profiles</span>
            <strong>{{ dashboard.total_profiles }}</strong>
            <p class="card-meta">Completed today</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon attendance">
            <i class="fas fa-check-circle"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Verified profiles</span>
            <strong>{{ dashboard.verified_profiles }}</strong>
            <p class="card-meta">Verified this week</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon treasury">
            <i class="fas fa-clock"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Pending updates</span>
            <strong>{{ dashboard.pending_updates }}</strong>
            <p class="card-meta">Awaiting review</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon approvals">
            <i class="fas fa-users"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Active members</span>
            <strong>{{ dashboard.active_members }}</strong>
            <p class="card-meta">Current active count</p>
          </div>
        </article>
      </div>''',
        'main': '''      <!-- Main Panels -->
      <div class="main-panels">
        <section class="panel module-status">
          <div class="panel-heading">
            <h2>Profile progress</h2>
            <a href="#">View all</a>
          </div>
          <div class="panel-list">
            {% for item in dashboard.profile_status %}
            <article class="panel-item">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.subtitle }}</p>
              </div>
              <span class="status-pill {{ item.status|lower }}">{{ item.status }}</span>
            </article>
            {% endfor %}
          </div>
        </section>

        <section class="panel attendance-chart">
          <div class="panel-heading">
            <h2>Verification trend</h2>
            <a href="#">Full report</a>
          </div>
          <div class="attendance-list">
            {% for event in dashboard.verification_trend %}
            <div class="attendance-row">
              <span>{{ event.label }}</span>
              <div class="attendance-bar-wrap">
                <div class="attendance-bar" style="--fill: {{ event.value }}%;"></div>
              </div>
              <strong>{{ event.value }}%</strong>
            </div>
            {% endfor %}
          </div>
        </section>
      </div>''',
        'lower': '''      <!-- Lower Panels -->
      <div class="lower-panels">
        <section class="panel approvals-list">
          <div class="panel-heading">
            <h2>Pending verifications</h2>
            <span class="items-count">{{ dashboard.pending_verifications|length }} items</span>
          </div>
          <div class="panel-list">
            {% for request_item in dashboard.pending_verifications %}
            <article class="panel-item approval-item">
              <div>
                <strong>{{ request_item.title }}</strong>
                <p>{{ request_item.subtitle }}</p>
              </div>
              <div class="approval-actions">
                <button class="btn-icon-action btn-approve" title="Approve"><i class="fas fa-check"></i></button>
                <button class="btn-icon-action btn-reject" title="Reject"><i class="fas fa-times"></i></button>
              </div>
            </article>
            {% endfor %}
          </div>
        </section>
      </div>''',
    },
    'Member_Dashboard_System/members': {
        'label': 'Member',
        'subtitle': "Access your profile, event attendance, and membership updates from one panel.",
        'modules': '''    <!-- Modules Section -->
      <div class="sidebar-section">
        <h3 class="sidebar-section-title">MY ACCOUNT</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item active">
            <i class="fas fa-user"></i>
            <span>PROFILE</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="members-profiles">
            <i class="fas fa-id-card"></i>
            <span>My Profile</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="members-status">
            <i class="fas fa-check-circle"></i>
            <span>Membership Status</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="members-history">
            <i class="fas fa-history"></i>
            <span>History</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h3 class="sidebar-section-title">EVENTS</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item feature-launcher" data-modal-key="attendance-events">
            <i class="fas fa-calendar"></i>
            <span>Upcoming Events</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="attendance-monitor">
            <i class="fas fa-chart-line"></i>
            <span>Attendance Log</span>
          </a>
        </nav>
      </div>''',
        'cards': '''      <!-- Overview Cards -->
      <div class="overview-cards">
        <article class="info-card">
          <div class="card-icon members">
            <i class="fas fa-user"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Membership status</span>
            <strong>{{ dashboard.membership_status }}</strong>
            <p class="card-meta">Current role</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon attendance">
            <i class="fas fa-calendar-check"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Events attended</span>
            <strong>{{ dashboard.events_attended }}</strong>
            <p class="card-meta">This semester</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon treasury">
            <i class="fas fa-money-bill-wave"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Dues status</span>
            <strong>{{ dashboard.dues_status }}</strong>
            <p class="card-meta">Updated today</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon approvals">
            <i class="fas fa-envelope"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Announcements</span>
            <strong>{{ dashboard.announcements }}</strong>
            <p class="card-meta">New messages</p>
          </div>
        </article>
      </div>''',
        'main': '''      <!-- Main Panels -->
      <div class="main-panels">
        <section class="panel module-status">
          <div class="panel-heading">
            <h2>Upcoming activities</h2>
            <a href="#">See schedule</a>
          </div>
          <div class="panel-list">
            {% for item in dashboard.upcoming_activities %}
            <article class="panel-item">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.subtitle }}</p>
              </div>
              <span class="status-pill {{ item.status|lower }}">{{ item.status }}</span>
            </article>
            {% endfor %}
          </div>
        </section>

        <section class="panel attendance-chart">
          <div class="panel-heading">
            <h2>Membership progress</h2>
            <a href="#">Details</a>
          </div>
          <div class="attendance-list">
            {% for event in dashboard.progress_metrics %}
            <div class="attendance-row">
              <span>{{ event.label }}</span>
              <div class="attendance-bar-wrap">
                <div class="attendance-bar" style="--fill: {{ event.value }}%;"></div>
              </div>
              <strong>{{ event.value }}%</strong>
            </div>
            {% endfor %}
          </div>
        </section>
      </div>''',
        'lower': '''      <!-- Lower Panels -->
      <div class="lower-panels">
        <section class="panel approvals-list">
          <div class="panel-heading">
            <h2>Latest notices</h2>
            <span class="items-count">{{ dashboard.recent_notices|length }} items</span>
          </div>
          <div class="panel-list">
            {% for notice in dashboard.recent_notices %}
            <article class="panel-item approval-item">
              <div>
                <strong>{{ notice.title }}</strong>
                <p>{{ notice.subtitle }}</p>
              </div>
            </article>
            {% endfor %}
          </div>
        </section>
      </div>''',
    },
    'Financial_System/Auditor': {
        'label': 'Auditor',
        'subtitle': "Review financial audits, flagged transactions, and compliance checks from one control panel.",
        'modules': '''    <!-- Modules Section -->
      <div class="sidebar-section">
        <h3 class="sidebar-section-title">AUDIT</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item active">
            <i class="fas fa-search"></i>
            <span>Audit Dashboard</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-file-invoice-dollar"></i>
            <span>Transaction Review</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-flag"></i>
            <span>Flagged Entries</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-balance-scale"></i>
            <span>Compliance Log</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h3 class="sidebar-section-title">REPORTS</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item">
            <i class="fas fa-chart-line"></i>
            <span>Audit Reports</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-calendar-check"></i>
            <span>Review Schedule</span>
          </a>
        </nav>
      </div>''',
        'cards': '''      <!-- Overview Cards -->
      <div class="overview-cards">
        <article class="info-card">
          <div class="card-icon members">
            <i class="fas fa-clipboard-list"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Pending audits</span>
            <strong>{{ dashboard.pending_audits }}</strong>
            <p class="card-meta">Require review</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon attendance">
            <i class="fas fa-file-alt"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Flagged transactions</span>
            <strong>{{ dashboard.flagged_transactions }}</strong>
            <p class="card-meta">Needs resolution</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon treasury">
            <i class="fas fa-check-circle"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Compliance score</span>
            <strong>{{ dashboard.compliance_score }}%</strong>
            <p class="card-meta">Last quarter</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon approvals">
            <i class="fas fa-user-shield"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Approval queue</span>
            <strong>{{ dashboard.approval_queue }}</strong>
            <p class="card-meta">Reviews pending</p>
          </div>
        </article>
      </div>''',
        'main': '''      <!-- Main Panels -->
      <div class="main-panels">
        <section class="panel module-status">
          <div class="panel-heading">
            <h2>Audit status</h2>
            <a href="#">View all</a>
          </div>
          <div class="panel-list">
            {% for item in dashboard.audit_status %}
            <article class="panel-item">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.subtitle }}</p>
              </div>
              <span class="status-pill {{ item.status|lower }}">{{ item.status }}</span>
            </article>
            {% endfor %}
          </div>
        </section>

        <section class="panel attendance-chart">
          <div class="panel-heading">
            <h2>Transaction risk</h2>
            <a href="#">Full report</a>
          </div>
          <div class="attendance-list">
            {% for event in dashboard.risk_trend %}
            <div class="attendance-row">
              <span>{{ event.label }}</span>
              <div class="attendance-bar-wrap">
                <div class="attendance-bar" style="--fill: {{ event.value }}%;"></div>
              </div>
              <strong>{{ event.value }}%</strong>
            </div>
            {% endfor %}
          </div>
        </section>
      </div>''',
        'lower': '''      <!-- Lower Panels -->
      <div class="lower-panels">
        <section class="panel approvals-list">
          <div class="panel-heading">
            <h2>Latest findings</h2>
            <span class="items-count">{{ dashboard.findings|length }} items</span>
          </div>
          <div class="panel-list">
            {% for finding in dashboard.findings %}
            <article class="panel-item approval-item">
              <div>
                <strong>{{ finding.title }}</strong>
                <p>{{ finding.subtitle }}</p>
              </div>
              <div class="approval-actions">
                <button class="btn-icon-action btn-approve" title="Review"><i class="fas fa-eye"></i></button>
              </div>
            </article>
            {% endfor %}
          </div>
        </section>
      </div>''',
    },
    'Financial_System/Treasurer': {
        'label': 'Treasurer',
        'subtitle': "Track cashflow, budgets, and receipts for the finance team efficiently.",
        'modules': '''    <!-- Modules Section -->
      <div class="sidebar-section">
        <h3 class="sidebar-section-title">FINANCE</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item active">
            <i class="fas fa-wallet"></i>
            <span>Finance Dashboard</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-file-invoice"></i>
            <span>Receipts</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-sack-dollar"></i>
            <span>Budget Planning</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-chart-line"></i>
            <span>Cashflow Report</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h3 class="sidebar-section-title">APPROVALS</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item">
            <i class="fas fa-check"></i>
            <span>Pending Payments</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-file-export"></i>
            <span>Export Statements</span>
          </a>
        </nav>
      </div>''',
        'cards': '''      <!-- Overview Cards -->
      <div class="overview-cards">
        <article class="info-card">
          <div class="card-icon members">
            <i class="fas fa-wallet"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Treasury balance</span>
            <strong>{{ dashboard.treasury_balance }}</strong>
            <p class="card-meta">Current available funds</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon attendance">
            <i class="fas fa-file-invoice-dollar"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Pending payments</span>
            <strong>{{ dashboard.pending_payments }}</strong>
            <p class="card-meta">Awaiting approval</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon treasury">
            <i class="fas fa-chart-pie"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Monthly revenue</span>
            <strong>{{ dashboard.monthly_revenue }}</strong>
            <p class="card-meta">This month</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon approvals">
            <i class="fas fa-file-alt"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Budget usage</span>
            <strong>{{ dashboard.budget_usage }}%</strong>
            <p class="card-meta">Against plan</p>
          </div>
        </article>
      </div>''',
        'main': '''      <!-- Main Panels -->
      <div class="main-panels">
        <section class="panel module-status">
          <div class="panel-heading">
            <h2>Financial summary</h2>
            <a href="#">View all</a>
          </div>
          <div class="panel-list">
            {% for item in dashboard.finance_status %}
            <article class="panel-item">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.subtitle }}</p>
              </div>
              <span class="status-pill {{ item.status|lower }}">{{ item.status }}</span>
            </article>
            {% endfor %}
          </div>
        </section>

        <section class="panel attendance-chart">
          <div class="panel-heading">
            <h2>Cashflow trend</h2>
            <a href="#">Full report</a>
          </div>
          <div class="attendance-list">
            {% for event in dashboard.cashflow_trend %}
            <div class="attendance-row">
              <span>{{ event.label }}</span>
              <div class="attendance-bar-wrap">
                <div class="attendance-bar" style="--fill: {{ event.value }}%;"></div>
              </div>
              <strong>{{ event.value }}%</strong>
            </div>
            {% endfor %}
          </div>
        </section>
      </div>''',
        'lower': '''      <!-- Lower Panels -->
      <div class="lower-panels">
        <section class="panel approvals-list">
          <div class="panel-heading">
            <h2>Recent transactions</h2>
            <span class="items-count">{{ dashboard.recent_transactions|length }} items</span>
          </div>
          <div class="panel-list">
            {% for tx in dashboard.recent_transactions %}
            <article class="panel-item approval-item">
              <div>
                <strong>{{ tx.title }}</strong>
                <p>{{ tx.subtitle }}</p>
              </div>
              <div class="approval-actions">
                <button class="btn-icon-action btn-approve" title="Review"><i class="fas fa-eye"></i></button>
              </div>
            </article>
            {% endfor %}
          </div>
        </section>
      </div>''',
    },
    'Document_Archiving_System/Secretary': {
        'label': 'Secretary',
        'subtitle': "Organize documents, archive official files, and manage document workflows.",
        'modules': '''    <!-- Modules Section -->
      <div class="sidebar-section">
        <h3 class="sidebar-section-title">DOCUMENTS</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item active">
            <i class="fas fa-folder-open"></i>
            <span>Document Dashboard</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="documents-memos">
            <i class="fas fa-file-lines"></i>
            <span>Memorandums</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="documents-minutes">
            <i class="fas fa-file-pen"></i>
            <span>Meeting Minutes</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="documents-archive">
            <i class="fas fa-archive"></i>
            <span>Archive</span>
          </a>
          <a href="#" class="nav-item feature-launcher" data-modal-key="documents-announcements">
            <i class="fas fa-bullhorn"></i>
            <span>Announcements</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h3 class="sidebar-section-title">RECORDS</h3>
        <nav class="sidebar-nav">
          <a href="#" class="nav-item feature-launcher" data-modal-key="documents-official">
            <i class="fas fa-file-shield"></i>
            <span>Official Documents</span>
          </a>
          <a href="#" class="nav-item">
            <i class="fas fa-clock"></i>
            <span>Recent Uploads</span>
          </a>
        </nav>
      </div>''',
        'cards': '''      <!-- Overview Cards -->
      <div class="overview-cards">
        <article class="info-card">
          <div class="card-icon members">
            <i class="fas fa-folder"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Pending files</span>
            <strong>{{ dashboard.pending_files }}</strong>
            <p class="card-meta">Need classification</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon attendance">
            <i class="fas fa-archive"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Archived records</span>
            <strong>{{ dashboard.archived_records }}</strong>
            <p class="card-meta">Total archive</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon treasury">
            <i class="fas fa-file-circle-check"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Minutes uploaded</span>
            <strong>{{ dashboard.meeting_minutes }}</strong>
            <p class="card-meta">This month</p>
          </div>
        </article>

        <article class="info-card">
          <div class="card-icon approvals">
            <i class="fas fa-paper-plane"></i>
          </div>
          <div class="card-content">
            <span class="card-label">Document requests</span>
            <strong>{{ dashboard.requests }}</strong>
            <p class="card-meta">Awaiting action</p>
          </div>
        </article>
      </div>''',
        'main': '''      <!-- Main Panels -->
      <div class="main-panels">
        <section class="panel module-status">
          <div class="panel-heading">
            <h2>Document workflow</h2>
            <a href="#">View all</a>
          </div>
          <div class="panel-list">
            {% for item in dashboard.document_status %}
            <article class="panel-item">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.subtitle }}</p>
              </div>
              <span class="status-pill {{ item.status|lower }}">{{ item.status }}</span>
            </article>
            {% endfor %}
          </div>
        </section>

        <section class="panel attendance-chart">
          <div class="panel-heading">
            <h2>Archive activity</h2>
            <a href="#">Report</a>
          </div>
          <div class="attendance-list">
            {% for event in dashboard.archive_activity %}
            <div class="attendance-row">
              <span>{{ event.label }}</span>
              <div class="attendance-bar-wrap">
                <div class="attendance-bar" style="--fill: {{ event.value }}%;"></div>
              </div>
              <strong>{{ event.value }}%</strong>
            </div>
            {% endfor %}
          </div>
        </section>
      </div>''',
        'lower': '''      <!-- Lower Panels -->
      <div class="lower-panels">
        <section class="panel approvals-list">
          <div class="panel-heading">
            <h2>Recent documents</h2>
            <span class="items-count">{{ dashboard.recent_documents|length }} items</span>
          </div>
          <div class="panel-list">
            {% for doc in dashboard.recent_documents %}
            <article class="panel-item approval-item">
              <div>
                <strong>{{ doc.title }}</strong>
                <p>{{ doc.subtitle }}</p>
              </div>
            </article>
            {% endfor %}
          </div>
        </section>
      </div>''',
    },
}

for path_str, data in roles.items():
    file_path = Path(path_str) / 'templates' / 'website' / 'dashboard.html'
    if not file_path.exists():
        print('Missing', file_path)
        continue
    content = file_path.read_text(encoding='utf-8')
    content = re.sub(r'<small>.*?</small>', f'<small>{data["label"]}</small>', content, count=1)
    content = re.sub(r'<p class="dashboard-subtitle">.*?</p>', f'<p class="dashboard-subtitle">{data["subtitle"]}</p>', content, count=1)
    content = re.sub(r'<!-- Modules Section -->.*?<!-- Administration Section -->', data['modules'] + '\n\n    <!-- Administration Section -->', content, flags=re.S)
    content = re.sub(r'<!-- Overview Cards -->.*?<!-- Main Panels -->', data['cards'] + '\n\n      <!-- Main Panels -->', content, flags=re.S)
    content = re.sub(r'<!-- Main Panels -->.*?<!-- Lower Panels -->', data['main'] + '\n\n      <!-- Lower Panels -->', content, flags=re.S)
    content = re.sub(r'<!-- Lower Panels -->.*?</div>\n    </section>', data['lower'] + '\n    </section>', content, flags=re.S)
    file_path.write_text(content, encoding='utf-8')
    print('Updated', file_path)
