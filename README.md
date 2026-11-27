# BrPH: Barangay Document Request and Processing System

A web-based, database-driven system where residents request barangay documents online
(Barangay Clearance, Certificate of Residency, Certificate of Indigency) and barangay
personnel review, process and track those requests.

**Stack:** Django (full-stack, Django templates) + PostgreSQL / Supabase

## Features
### PD1: Account Feature
Registration, login/logout, role-based dashboards (Resident, Barangay Admin), user profile.

### PD2: Core Feature, Document Request Processing
**Resident**
- Browse active document types and their requirements
- Submit a request (purpose, copies, pickup date) and upload the required files (PDF/JPG/PNG, max 5 MB)
- View own requests, filter by status, see status history
- Edit, cancel or delete a request while it is still *Pending* (delete also allowed when *Cancelled*)

**Barangay Admin**
- Dashboard with request counts and newest pending requests
- Search and filter all requests (reference no., resident, status, document type)
- Review uploaded files and move a request through
  `Pending -> Under Review -> Approved -> Ready for Pickup -> Released` (or `Rejected`, which needs a reason)
- Full CRUD for document types and their requirements

**Business rules:** one active request per document type per resident, pickup date cannot be in the past,
mandatory requirements must be uploaded, residents can only see and change their own records.

**Models:** `User` (accounts) 1-N `DocumentRequest` N-1 `DocumentType` 1-N `Requirement`;
`DocumentRequest` 1-N `RequestAttachment` and 1-N `StatusHistory`.

## Setup
```bash
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env  (then fill in DATABASE_URL)
python manage.py migrate
python manage.py seed_document_types
python manage.py createsuperuser # superusers get the Barangay Admin role
python manage.py runserver
```

### Run the automated tests
```bash
python manage.py test                 # all tests (47)
python manage.py test documents       # core feature only
python manage.py test accounts        # standard features (register, login, dashboard, profile)
```
Tests live in `documents/tests/` (`test_core_flow.py`, `test_hardening.py`) and `accounts/tests.py`.
They create their own temporary test database and temporary media folder, so no real data is touched.
Your `.env` needs a working `DATABASE_URL` (PostgreSQL role must be allowed to create a test database).

### PD3 Hardening summary
- **Validation:** server-side rules on every form (copies 1-5, pickup date not past / within 90 days,
  file type + content check, unique names, phone format); clear success/error messages.
- **Errors:** custom 404, 403, CSRF and 500 pages; invalid or huge IDs return 404.
- **Security:** login + role check inside every view; own-records-only queries; POST-only changes with CSRF;
  private attachments served through `/files/<id>/`; `DEBUG` and secrets from `.env`.
- **Integrity:** DB constraints (one active request per type, copies range, unique files/requirements),
  `PROTECT` on resident/document type, `transaction.atomic()`, redirect-after-POST, delete confirmation pages.
- **Files:** set `USE_SUPABASE_STORAGE=True` (see `.env.example`) to keep uploads in a private Supabase bucket.

## Roles and URLs
| Role | Dashboard |
|------|-----------|
| Resident (public registration at `/register/`) | `/dashboard/resident/` |
| Barangay Admin (created with `createsuperuser`) | `/dashboard/staff/` |

## Branching
`main` (stable) <- `develop` (integration) <- `feature/*`, `fix/*`, `hardening/*`, `test/*` branches, merged by Pull Request.
