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
Run tests: `python manage.py test`

## Roles and URLs
| Role | Dashboard |
|------|-----------|
| Resident (public registration at `/register/`) | `/dashboard/resident/` |
| Barangay Admin (created with `createsuperuser`) | `/dashboard/staff/` |

## Branching
`main` (stable) <- `develop` (integration) <- `feature/*` branches, merged by Pull Request.
