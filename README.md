# Nova Construct - Real Estate Construction Management & Digital Work Diary System

An enterprise-grade, production-oriented multi-project construction management portal and digital work diary system built with Python, Django, PostgreSQL, and Bootstrap 5.

Designed with inspiration from the **Nova Astro** editorial architectural aesthetic by ThemeWagon, featuring clean typography, generous whitespace, warm off-white tones, deep navy accents, and robust operational capabilities.

---

## 1. Architectural Architecture & Design

### Technology Stack
- **Backend:** Python 3.14+, Django 5.1+ / 6.1+
- **Database:** PostgreSQL (with `psycopg` 3.3+ binary driver) & SQLite development fallback
- **Frontend:** Django Templates, HTML5, CSS3, JavaScript
- **UI Framework:** Bootstrap 5.3 + Bootstrap Icons
- **Design System:** Nova Architectural Theme (`/static/css/nova-theme.css`)
- **Charts:** Chart.js 4.4+
- **Asynchronous & Scheduled Tasks:** Celery + Redis
- **Security:** CSRF, Session Cookie HttpOnly/SameSite Lax, X-Frame-Options DENY, Role-based server-side checks

---

## 2. Role-Based Access Control (RBAC) & Permissions

The system implements 7 distinct roles with strict server-side authorization:

| Role | Code | Scope & Capabilities |
| :--- | :--- | :--- |
| **Super Administrator** | `SUPER_ADMIN` | Global access to all projects, user approval, system settings, financial overrides. |
| **Company Administrator** | `COMPANY_ADMIN` | Global visibility across all corporate projects, budget approvals, and staff assignments. |
| **Project Manager** | `PROJECT_MANAGER` | Full operational control of assigned projects, schedules, purchase approvals, task allocation. |
| **Accountant** | `ACCOUNTANT` | Financial ledger entries, payment allocations, invoice reconciliations, supplier dues tracking. |
| **Legal Officer** | `LEGAL_OFFICER` | Compliance documents, statutory clearances, contract versions, expiry monitoring. |
| **Site Supervisor** | `SITE_SUPERVISOR` | Daily labour logs, attendance, site photo uploads, daily diary reports via web and QR portal. |
| **Read-only Auditor** | `AUDITOR` | Read-only inspection of ledgers, audit logs, reports, and compliance records. |

---

## 3. Directory Structure

```
d:/WorkBook/
├── config/
│   ├── settings.py           # Django settings (12-Factor, PostgreSQL + SQLite fallback)
│   ├── urls.py               # Root URLconf
│   ├── wsgi.py               # WSGI application entrypoint
│   └── asgi.py               # ASGI application entrypoint
├── apps/
│   ├── accounts/             # Custom User model, RBAC, project memberships, permissions
│   │   ├── models.py         # User, RoleChoices, ProjectMembership
│   │   ├── permissions.py    # Decorators: project_access_required, project_role_required
│   │   ├── views.py          # login_view, logout_view, profile_view, user_list_view
│   │   ├── forms.py          # LoginForm, UserProfileForm, ProjectMembershipForm
│   │   ├── urls.py           # /accounts/login/, /accounts/logout/, /accounts/profile/
│   │   └── tests.py          # Unit & integration tests for authentication and RBAC
│   └── projects/             # Core Project entity, lifecycle, financial aggregates
│       ├── models.py         # Project model, Status choices, financial calculation methods
│       ├── views.py          # Project list, detail, and create placeholders
│       └── urls.py           # /projects/ routes
├── static/
│   └── css/
│       └── nova-theme.css    # Nova Astro inspired editorial design system tokens
├── templates/
│   ├── base.html             # Base layout with Outfit & Plus Jakarta Sans typography
│   ├── components/
│   │   ├── navbar.html       # Brand header, role indicator, navigation dropdown
│   │   ├── messages.html     # Dismissible feedback alerts
│   │   └── footer.html       # Corporate footer
│   ├── accounts/
│   │   ├── login.html        # Editorial login card with security badges
│   │   ├── profile.html      # User profile & assigned projects matrix
│   │   └── user_list.html    # Staff governance & role directory
│   └── projects/             # Project templates
├── .env.example              # Environment variables template
├── requirements.txt          # Production dependencies
└── manage.py
```

---

## 4. Development Milestones & Progress Tracker

- [x] **Stage 1: Project Setup, PostgreSQL Driver, Authentication & Roles** *(Completed)*
  - Initialized Django project with modular `apps/` layout.
  - Configured PostgreSQL database engine (`psycopg` v3) with environment variables and seamless SQLite local fallback.
  - Created `.env` and `.env.example`.
  - Implemented custom `User` model with 7 roles and administrator approval flag.
  - Created `ProjectMembership` model linking users to specific construction projects with custom roles.
  - Implemented server-side security decorators: `project_access_required`, `project_role_required`, `admin_or_manager_required`.
  - Designed Nova Astro inspired layout, typography, and styling.
  - Implemented `seed_demo_data` command with demo accounts across all roles.
  - Wrote and verified automated test suite: 7/7 tests passing with zero warnings.
- [ ] **Stage 2: Project Homepage, Create-Project Form & Project Dashboard**
- [ ] **Stage 3: Labour Daily Diary & Wage Calculations**
- [ ] **Stage 4: Material Purchases, Delivery Tracking & Supplier Payments**
- [ ] **Stage 5: Central Financial Ledger & Automatic Budget Calculations**
- [ ] **Stage 6: Budget Allocation & Interactive Charts**
- [ ] **Stage 7: Related People & Secure Legal Document Management**
- [ ] **Stage 8: Daily Site Reports & Image Gallery**
- [ ] **Stage 9: Weekly Work Planning & Progress Tracking**
- [ ] **Stage 10: Supervisor QR Portal & Restricted Uploads**
- [ ] **Stage 11: Notifications, Exports & Management Reports**
- [ ] **Stage 12: Full Regression Testing, Security Review & Deployment Verification**

---

## 5. Getting Started & Running Tests

### 1. Seed Demo Credentials
```bash
python manage.py seed_demo_data
```
Standard seeded test accounts (password for all demo accounts: `Admin@12345`):
- `superadmin` (Super Administrator)
- `companyadmin` (Company Administrator)
- `pm_lead` (Project Manager)
- `accountant` (Accountant)
- `legal_officer` (Legal Officer)
- `supervisor` (Site Supervisor)
- `auditor` (Read-only Auditor)

### 2. Run Automated Tests
```bash
python manage.py test
```

### 3. Run Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Visit: [http://127.0.0.1:8000/accounts/login/](http://127.0.0.1:8000/accounts/login/)
