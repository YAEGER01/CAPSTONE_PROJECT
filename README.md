# ISU-CAUFA Cooperative Management Portal

A role-based cooperative management web portal for the **Isabela State University - Cooperative Association of University Faculty and Administrators (ISU-CAUFA)**. This system digitizes the financial and administrative workflows of the cooperative, providing a complete audit trail for all transactions.

## Purpose

The portal replaces manual record-keeping with a centralized digital system that allows cooperative officers to manage members, process fees and dues, handle medical/death aid claims, and perform audit verifications — all with cryptographic integrity assurances and a full audit trail.

## Roles & Workflow

The system implements a **three-role approval pipeline**:

| Role          | Responsibilities                                                                                                                                                           |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Treasurer** | Enroll/update/retire members, record membership fees (Full/Partial), monthly dues (OTC cash, GCash, Salary Deduction), file medical/death aid claims, release approved aid |
| **Auditor**   | Review pending payments and aid claims, verify or return for revision, upload supporting evidence                                                                          |
| **President** | Final approval of auditor-verified payments and aid claims, set approved amounts, approve or reject                                                                        |

Each transaction flows through **Treasurer → Auditor → President** before finalization.

## Key Features

- **Member Management** — Full lifecycle (enrollment, updates, retirement)
- **Membership Fees** — Record full or partial payments with supporting proof documents
- **Monthly Dues** — Over-the-counter (Cash/GCash/Cashier Handover) and Salary Deduction modes
- **Medical Aid Claims** — File and process accidental/sickness aid (up to PHP 20,000)
- **Death Aid Claims** — Bereavement aid with tiered amounts (PHP 100–500)
- **Audit Verification** — Auditor reviews all transactions with rejection/revision workflow
- **Presidential Approval** — Final sign-off on verified payments and aid
- **Global Audit Trail** — Every action logged with old/new snapshots, actor info, IP address
- **Supporting Proof System** — File uploads with SHA-256 hashing and HMAC row signatures for integrity verification
- **Email Notifications** — Members notified via Gmail SMTP for fee confirmations, corrections, and policy exceptions
- **Policy Enforcement** — Cooperative by-laws (ARTICLE XI) enforced: standing requirements, fee amounts, exemption rules

## Tech Stack

| Layer              | Technology                                             |
| ------------------ | ------------------------------------------------------ |
| **Backend**        | Django 5.1+ (Python)                                   |
| **Database**       | MySQL 8+                                               |
| **Frontend**       | HTML, CSS, Vanilla JS (SPA dashboards)                 |
| **Authentication** | Custom session-based (SHA-256, `ACCESS_SESSION` table) |
| **File Storage**   | Django `FileField` / local `media/` directory          |
| **Email**          | Gmail SMTP                                             |
| **Testing**        | pytest + pytest-django                                 |

## Directory Layout

```
├── caufa_portal/              # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py / asgi.py
├── core_system/               # Main Django app (business logic)
│   ├── models.py              # 20+ database models
│   ├── views.py               # Treasurer & President views
│   ├── views_auditor_api.py   # Auditor views
│   ├── auth_views.py          # Custom login
│   ├── guards.py              # Role-based access decorators
│   ├── services/              # Business logic (policy, fees, notifications)
│   ├── constants/             # Policy constants (fee amounts, thresholds)
│   └── tests.py
├── templates/                 # Django templates
│   ├── website/index.html     # Landing page
│   ├── website/login.html     # Login page
│   ├── website/Treasurer/     # Treasurer dashboard (4434 lines)
│   ├── website/Auditor/       # Auditor dashboard
│   └── website/President/     # President dashboard
├── static/                    # CSS, JS, images
│   ├── css/
│   ├── js/
│   └── img/
└── media/                     # File uploads
```

## Getting Started

### Prerequisites

- Python 3.10+
- MySQL 8+
- Gmail account (for email notifications)

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd CAPSTONE_PROJECT

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Edit .env with your database credentials and email settings

# Run database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

### Default Officer Accounts

| Username          | Password                   |
| ----------------- | -------------------------- |
| `president_admin` | `SecurePresidentPass2026!` |
| `auditor_admin`   | `SecureAuditorPass2026!`   |
| `treasurer_admin` | `SecureTreasurerPass2026!` |

### Running Tests

```bash
pytest
```

## Environment Variables

Key variables in `.env`:

- `SECRET_KEY` — Django secret key
- `DATABASE_URL` — MySQL connection string
- `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` — Gmail SMTP credentials
- `TIME_ZONE` — Defaults to `Asia/Manila`

## API Endpoints

All routes are defined in `core_system/urls.py` under:

- `/api/treasurer/*` — Treasurer operations
- `/api/auditor/*` — Auditor review operations
- `/api/president/*` — Presidential approval operations
- `/api/audit/trail/<table>/<id>/` — Audit trail viewer

## Data Model

20+ database tables including: `MEMBER`, `MONTHLY_DUES`, `MEMBERSHIP_FEE`, `MEDICAL_AID`, `DEATH_AID`, `TRANSACTION_VERIFICATION`, `GLOBAL_AUDIT_TRAIL`, and more. All models use explicit `db_table` names matching the legacy SQL schema.

## License

This project was developed as a capstone requirement.
