# CarePoint Hospital Management System

Django 5 + MySQL hospital management system with secure role-based access for **Administrator, Doctor, Receptionist and Patient**.

## Project structure

```
hms/            settings (env-driven), root urls, wsgi
accounts/       custom User (role field), login/logout/register, role decorator, user & role management
doctors/        Department, Doctor (+ login account), directory
patients/       Patient (personal info, emergency contact, blood group, allergies, history), access rules
appointments/   Appointment, double-booking prevention, status workflow, check-in, free-slot JSON endpoint
records/        MedicalRecord + Prescription (diagnosis, treatment, notes, follow-up)
admissions/     Bed (rooms/beds), Admission, discharge (auto room-charge invoice)
billing/        Bill, BillItem, Payment, invoice + printable view, auto payment status
dashboard/      role-specific dashboards, global search, seed_demo command, integration tests
templates/      base layout, partials, per-app templates      static/  css/style.css, js/app.js
```

## Database schema (relationships)

```
User 1─1 Doctor ─N─1 Department          User 1─0..1 Patient
Patient 1─N Appointment N─1 Doctor       Appointment N─1 Department
Patient 1─N MedicalRecord N─1 Doctor     MedicalRecord 0..1─1 Appointment
MedicalRecord 1─N Prescription
Bed 1─N Admission N─1 Patient            Admission N─1 Doctor (attending)
Patient 1─N Bill 1─N BillItem            Bill 1─N Payment
Bill N─0..1 Appointment / Admission
```

## Setup

### 1. Python and virtual environment
Python 3.10+ is required.
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
`mysqlclient` needs MySQL client headers. Ubuntu/Debian: `sudo apt install build-essential pkg-config default-libmysqlclient-dev python3-dev`; macOS: `brew install mysql-client pkg-config`; Windows normally installs a prebuilt wheel.

### 2. MySQL database
```sql
CREATE DATABASE hospital_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hms_user'@'localhost' IDENTIFIED BY 'a-strong-password';
GRANT ALL PRIVILEGES ON hospital_db.* TO 'hms_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Environment variables
```bash
cp .env.example .env     # then edit DB_USER / DB_PASSWORD / DJANGO_SECRET_KEY
```
Generate a secret key: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`.
(For a quick trial without MySQL set `DB_ENGINE=sqlite`. Use MySQL for real deployments.)

### 4. Migrate, create the first administrator, run
```bash
python manage.py migrate
python manage.py createsuperuser          # automatically gets the Administrator role
python manage.py runserver
```
Open http://127.0.0.1:8000/ and sign in.

### Optional: demo data
```bash
python manage.py seed_demo
```
Creates departments, doctors, patients, beds, appointments, a record and a bill. Logins (all with password `Hospital@123`, **development only**): `admin`, `reception`, `dr.rao`, `dr.khan`, `dr.nair`, `patient1`.

### Tests
```bash
DB_ENGINE=sqlite python manage.py test     # 18 tests: permissions, double-booking, privacy, billing
```

## Who can do what

| Area | Admin | Doctor | Receptionist | Patient |
|---|---|---|---|---|
| Users & roles, departments, doctors, beds | manage | view doctors | view doctors / beds | view doctors |
| Patients | full | assigned patients only | register, edit, search | own profile (limited edit) |
| Appointments | all, any status | own; confirm / complete / cancel | schedule, update, cancel, check-in | request, view own, cancel own |
| Records & prescriptions | view | write & edit own; read assigned patients' history | **no access** | read own |
| Admissions | all | own patients, discharge | admit, discharge | view own |
| Billing | full | **no access** | create, edit, record payments | view own, print |

Access is enforced server-side (`accounts/decorators.py` and `patients/permissions.py`); records outside a user's scope return 404 so their existence is not revealed.

## Key behaviours
- **Double-booking**: 30-minute slots; overlapping non-cancelled appointments for the same doctor are rejected in forms and again in `Appointment.save()` under a row lock (`select_for_update`). Bookings must fall within the doctor's working hours and in the future.
- **Patient requests** start as *Pending*; staff or the doctor confirms them to *Scheduled*.
- **Billing**: payment status (Pending / Partially Paid / Paid) is recalculated automatically whenever items, discount or payments change; overpayment is blocked. Discharging a patient creates the room-charge line (nights × daily rate).
- **JavaScript** (`static/js/app.js`) is optional enhancement: date/time validation, department→doctor filtering, live free-slot picker, confirmation dialogs, table filtering, AJAX status updates, dynamic bill/prescription rows with live totals.

## Production notes
Set `DJANGO_DEBUG=False`, a real `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, run `python manage.py collectstatic`, serve behind HTTPS with gunicorn/uWSGI + a static file server. With debug off the settings enable secure cookies, HSTS and SSL redirect. Amounts are stored as decimals with no currency symbol; set `TIME_ZONE` in `.env` (e.g. `Asia/Kolkata`).
