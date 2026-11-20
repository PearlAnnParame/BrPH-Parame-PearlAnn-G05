# BrPH: Barangay Document Request and Processing System

Django (full-stack) + PostgreSQL/Supabase. PD1: Account Feature.

## Setup
```bash
python -m venv venv
venv\Scripts\activate        # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env       # then edit DATABASE_URL (macOS/Linux: cp)
python manage.py migrate
python manage.py createsuperuser   # superusers become Barangay Admins
python manage.py runserver
```
## Roles
- **Resident**: public registration, goes to `/dashboard/resident/`
- **Barangay Admin**: created via `createsuperuser` or Django admin (`/django-admin/`), goes to `/dashboard/staff/`
