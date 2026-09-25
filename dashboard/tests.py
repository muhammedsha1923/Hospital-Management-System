"""Integration tests: role permissions, double-booking, record privacy, billing and page smoke tests."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from admissions.models import Admission, Bed
from appointments.models import Appointment
from billing.models import Bill, BillItem, Payment
from doctors.models import Department, Doctor
from patients.models import Patient
from records.models import MedicalRecord, Prescription

PW = "S3cure-Pass!9"


def make_user(username, role, **kw):
    return User.objects.create_user(username=username, password=PW, role=role, first_name=username.title(), last_name="Test", email=f"{username}@x.com", **kw)


class BaseCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name="Cardiology")
        cls.admin = make_user("admin1", "ADMIN")
        cls.recep = make_user("recep1", "RECEPTIONIST")
        cls.doc_user = make_user("doc1", "DOCTOR")
        cls.doc2_user = make_user("doc2", "DOCTOR")
        cls.doctor = Doctor.objects.create(user=cls.doc_user, department=cls.dept, specialization="Cardio", license_number="L1", consultation_fee=500)
        cls.doctor2 = Doctor.objects.create(user=cls.doc2_user, department=cls.dept, specialization="Cardio", license_number="L2", consultation_fee=300)
        cls.pat_user = make_user("pat1", "PATIENT")
        cls.patient = Patient.objects.create(user=cls.pat_user, first_name="Pat", last_name="One", date_of_birth="1990-01-01", gender="F", phone="1")
        cls.other_user = make_user("pat2", "PATIENT")
        cls.other = Patient.objects.create(user=cls.other_user, first_name="Other", last_name="Person", date_of_birth="1985-01-01", gender="M", phone="2")
        cls.tomorrow = timezone.localdate() + timedelta(days=1)

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PW))

    def appt(self, time="10:00", patient=None, doctor=None, status="SCHEDULED"):
        return Appointment.objects.create(patient=patient or self.patient, doctor=doctor or self.doctor, department=self.dept,
                                          date=self.tomorrow, time=time, reason="Checkup", status=status)


class AppointmentRules(BaseCase):
    def test_double_booking_is_blocked(self):
        self.appt("10:00")
        with self.assertRaises(ValidationError):
            self.appt("10:15", patient=self.other)      # overlaps the 10:00-10:30 slot
        self.appt("10:30", patient=self.other)          # back-to-back is fine
        self.appt("10:00", patient=self.other, doctor=self.doctor2)  # different doctor is fine

    def test_cancelled_slot_can_be_rebooked(self):
        a = self.appt("11:00")
        a.status = "CANCELLED"; a.save()
        self.appt("11:00", patient=self.other)

    def test_form_rejects_conflict_and_out_of_hours(self):
        self.appt("10:00")
        self.login(self.recep)
        data = dict(patient=self.other.pk, department=self.dept.pk, doctor=self.doctor.pk, date=self.tomorrow, time="10:00", reason="x", status="SCHEDULED")
        r = self.client.post(reverse("appointments:create"), data)
        self.assertContains(r, "already has an appointment")
        r = self.client.post(reverse("appointments:create"), {**data, "time": "22:00"})
        self.assertContains(r, "sees patients between")
        self.assertEqual(Appointment.objects.count(), 1)

    def test_past_dates_rejected(self):
        self.login(self.recep)
        data = dict(patient=self.other.pk, department=self.dept.pk, doctor=self.doctor.pk, date=timezone.localdate() - timedelta(days=1), time="10:00", reason="x", status="SCHEDULED")
        self.assertContains(self.client.post(reverse("appointments:create"), data), "must be in the future")

    def test_patient_request_is_pending_and_can_cancel_only_own(self):
        self.login(self.pat_user)
        r = self.client.post(reverse("appointments:create"), dict(department=self.dept.pk, doctor=self.doctor.pk, date=self.tomorrow, time="09:00", reason="Chest pain"))
        self.assertEqual(r.status_code, 302)
        a = Appointment.objects.get()
        self.assertEqual((a.status, a.patient), ("PENDING", self.patient))
        self.login(self.other_user)
        self.assertEqual(self.client.post(reverse("appointments:status", args=[a.pk]), {"status": "CANCELLED"}).status_code, 404)
        self.login(self.pat_user)
        self.client.post(reverse("appointments:status", args=[a.pk]), {"status": "CANCELLED"})
        a.refresh_from_db(); self.assertEqual(a.status, "CANCELLED")

    def test_status_ajax_and_checkin(self):
        a = self.appt("09:00")
        a.date = timezone.localdate(); a.time = "23:00"; Appointment.objects.filter(pk=a.pk).update(date=a.date, time=a.time)
        self.login(self.recep)
        r = self.client.post(reverse("appointments:checkin", args=[a.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(r.json()["ok"]); a.refresh_from_db(); self.assertIsNotNone(a.checked_in_at)
        r = self.client.post(reverse("appointments:status", args=[a.pk]), {"status": "CANCELLED"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.json()["status"], "CANCELLED")

    def test_slots_endpoint(self):
        self.appt("09:00")
        self.login(self.pat_user)
        data = self.client.get(reverse("appointments:slots"), {"doctor": self.doctor.pk, "date": self.tomorrow.isoformat()}).json()
        by_time = {s["time"]: s["free"] for s in data["slots"]}
        self.assertFalse(by_time["09:00"]); self.assertTrue(by_time["09:30"])


class Privacy(BaseCase):
    def setUp(self):
        self.appt("10:00")  # doctor1 <-> patient
        self.record = MedicalRecord.objects.create(patient=self.patient, doctor=self.doctor, diagnosis="Secret diagnosis")
        Prescription.objects.create(record=self.record, medication="Aspirin", dosage="75mg", frequency="daily")

    def test_doctor_sees_only_assigned_patients(self):
        self.login(self.doc_user)
        self.assertContains(self.client.get(reverse("patients:list")), "Pat One")
        self.assertNotContains(self.client.get(reverse("patients:list")), "Other Person")
        self.assertEqual(self.client.get(reverse("patients:detail", args=[self.other.pk])).status_code, 404)
        self.login(self.doc2_user)  # not assigned to Pat
        self.assertEqual(self.client.get(reverse("patients:detail", args=[self.patient.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("records:detail", args=[self.record.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("records:create", args=[self.patient.pk])).status_code, 404)

    def test_patient_sees_only_own_data(self):
        self.login(self.other_user)
        self.assertEqual(self.client.get(reverse("patients:detail", args=[self.patient.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("records:detail", args=[self.record.pk])).status_code, 404)
        self.login(self.pat_user)
        self.assertContains(self.client.get(reverse("records:detail", args=[self.record.pk])), "Secret diagnosis")

    def test_receptionist_cannot_read_clinical_data(self):
        self.login(self.recep)
        self.assertEqual(self.client.get(reverse("records:detail", args=[self.record.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("patients:detail", args=[self.patient.pk])), "Secret diagnosis")

    def test_role_gates(self):
        gates = [(self.pat_user, "accounts:user_list"), (self.doc_user, "accounts:user_list"), (self.recep, "accounts:user_list"),
                 (self.pat_user, "patients:list"), (self.pat_user, "doctors:create"), (self.recep, "doctors:create"),
                 (self.doc_user, "billing:list"), (self.doc_user, "patients:create"), (self.pat_user, "admissions:admit")]
        for user, name in gates:
            self.login(user)
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, f"{user.role} -> {name}")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("patients:list")).status_code, 302)

    def test_doctor_writes_record_and_completes_appointment(self):
        self.login(self.doc_user)
        a = Appointment.objects.get()
        data = {"visit_date": self.tomorrow, "diagnosis": "Flu", "symptoms": "", "treatment": "", "notes": "", "follow_up_date": self.tomorrow + timedelta(days=7),
                "mark_completed": "on", "prescriptions-TOTAL_FORMS": 1, "prescriptions-INITIAL_FORMS": 0, "prescriptions-MIN_NUM_FORMS": 0, "prescriptions-MAX_NUM_FORMS": 1000,
                "prescriptions-0-medication": "Paracetamol", "prescriptions-0-dosage": "500mg", "prescriptions-0-frequency": "TID", "prescriptions-0-duration": "3 days", "prescriptions-0-instructions": ""}
        r = self.client.post(reverse("records:create", args=[self.patient.pk]) + f"?appointment={a.pk}", data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        a.refresh_from_db(); self.assertEqual(a.status, "COMPLETED")
        self.assertEqual(Prescription.objects.filter(medication="Paracetamol").count(), 1)


class Billing(BaseCase):
    def test_payment_status_flow(self):
        bill = Bill.objects.create(patient=self.patient)
        BillItem.objects.create(bill=bill, category="CONSULTATION", description="Consult", quantity=1, unit_price=500)
        BillItem.objects.create(bill=bill, category="MEDICINE", description="Pills", quantity=2, unit_price=50)
        bill.refresh_from_db()
        self.assertEqual((bill.total, bill.status), (Decimal("600"), "PENDING"))
        self.assertTrue(bill.invoice_number.startswith("INV-"))
        self.login(self.recep)
        self.client.post(reverse("billing:pay", args=[bill.pk]), {"amount": "200", "method": "CASH", "paid_on": timezone.localdate()})
        bill.refresh_from_db(); self.assertEqual(bill.status, "PARTIAL")
        r = self.client.post(reverse("billing:pay", args=[bill.pk]), {"amount": "999", "method": "CASH", "paid_on": timezone.localdate()}, follow=True)
        self.assertContains(r, "exceeds the outstanding balance")
        self.client.post(reverse("billing:pay", args=[bill.pk]), {"amount": "400", "method": "CARD", "paid_on": timezone.localdate()})
        bill.refresh_from_db(); self.assertEqual(bill.status, "PAID")

    def test_patient_sees_only_own_bills(self):
        bill = Bill.objects.create(patient=self.patient)
        BillItem.objects.create(bill=bill, category="LAB", description="CBC", quantity=1, unit_price=100)
        self.login(self.other_user)
        self.assertEqual(self.client.get(reverse("billing:detail", args=[bill.pk])).status_code, 404)
        self.login(self.pat_user)
        self.assertContains(self.client.get(reverse("billing:detail", args=[bill.pk])), "CBC")
        self.assertContains(self.client.get(reverse("billing:print", args=[bill.pk])), "CBC")

    def test_admission_discharge_generates_room_bill(self):
        bed = Bed.objects.create(room_number="1", bed_number="A", daily_rate=1000)
        self.login(self.recep)
        r = self.client.post(reverse("admissions:admit"), {"patient": self.patient.pk, "bed": bed.pk, "attending_doctor": self.doctor.pk, "reason": "Surgery"})
        self.assertEqual(r.status_code, 302)
        adm = Admission.objects.get(); self.assertTrue(bed.is_occupied)
        r = self.client.post(reverse("admissions:admit"), {"patient": self.other.pk, "bed": bed.pk, "attending_doctor": self.doctor.pk, "reason": "x"})
        self.assertEqual(r.status_code, 200)  # bed no longer offered
        Admission.objects.filter(pk=adm.pk).update(admitted_at=timezone.now() - timedelta(days=2))
        self.client.post(reverse("admissions:discharge", args=[adm.pk]))
        adm.refresh_from_db(); self.assertEqual(adm.status, "DISCHARGED")
        bill = Bill.objects.get(admission=adm)
        self.assertEqual(bill.total, Decimal("2000"))  # 2 nights x 1000
        self.assertFalse(bed.is_occupied)


class Smoke(BaseCase):
    """Every page renders for every role that may open it."""

    def test_pages_render(self):
        a = self.appt("10:00")
        rec = MedicalRecord.objects.create(patient=self.patient, doctor=self.doctor, diagnosis="D")
        bed = Bed.objects.create(room_number="2", bed_number="1", daily_rate=10)
        bill = Bill.objects.create(patient=self.patient); BillItem.objects.create(bill=bill, description="x", quantity=1, unit_price=5)
        common = ["dashboard:home", "appointments:list", "doctors:list", "accounts:profile", "accounts:password_change"]
        pages = {
            self.admin: common + ["patients:list", "patients:create", "doctors:create", "doctors:departments", "doctors:department_create", "accounts:user_list",
                                  "accounts:user_create", "admissions:list", "admissions:admit", "admissions:beds", "admissions:bed_create", "billing:list", "billing:create",
                                  "appointments:create", "dashboard:search"],
            self.recep: common + ["patients:list", "patients:create", "admissions:list", "admissions:admit", "admissions:beds", "billing:list", "billing:create", "appointments:create", "dashboard:search"],
            self.doc_user: common + ["patients:list", "admissions:list"],
            self.pat_user: common + ["patients:me", "records:mine", "billing:list", "appointments:create", "admissions:list"],
        }
        for user, names in pages.items():
            self.login(user)
            for name in names:
                r = self.client.get(reverse(name))
                self.assertEqual(r.status_code in (200, 302), True, f"{user.role} {name} -> {r.status_code}")
        for user in (self.admin, self.recep):
            self.login(user)
            for name, args in [("patients:detail", [self.patient.pk]), ("patients:edit", [self.patient.pk]), ("appointments:detail", [a.pk]), ("appointments:edit", [a.pk]),
                               ("billing:detail", [bill.pk]), ("billing:edit", [bill.pk]), ("billing:print", [bill.pk]), ("doctors:detail", [self.doctor.pk])]:
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, f"{user.role} {name}")
        self.login(self.admin)
        for name, args in [("records:detail", [rec.pk]), ("admissions:bed_edit", [bed.pk]), ("doctors:edit", [self.doctor.pk]), ("accounts:user_edit", [self.doc_user.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        self.login(self.doc_user)
        for name, args in [("records:create", [self.patient.pk]), ("appointments:detail", [a.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)


class Registration(BaseCase):
    def test_public_registration_creates_patient_only(self):
        self.client.logout()
        r = self.client.post(reverse("accounts:register"), dict(first_name="New", last_name="Person", username="newp", email="newp@x.com", phone="123",
                                                                password1=PW, password2=PW, date_of_birth="1999-05-05", gender="F", blood_group="A+", address=""))
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="newp")
        self.assertEqual(u.role, "PATIENT"); self.assertTrue(u.patient_profile.patient_id.startswith("PT"))
        self.assertNotEqual(u.password, PW)  # hashed
        # cannot inject a role through the form
        self.client.logout()
        self.client.post(reverse("accounts:register"), dict(first_name="Ev", last_name="Il", username="evil", email="e@x.com", phone="1", password1=PW, password2=PW,
                                                            date_of_birth="1999-05-05", gender="M", role="ADMIN"))
        self.assertEqual(User.objects.get(username="evil").role, "PATIENT")

    def test_admin_role_management(self):
        self.login(self.admin)
        r = self.client.post(reverse("accounts:user_edit", args=[self.recep.pk]), dict(first_name="R", last_name="T", email="r@x.com", phone="", role="ADMIN", is_active="on"))
        self.assertEqual(r.status_code, 302); self.recep.refresh_from_db(); self.assertEqual(self.recep.role, "ADMIN")
        r = self.client.post(reverse("accounts:user_edit", args=[self.doc_user.pk]), dict(first_name="D", last_name="T", email="d@x.com", phone="", role="RECEPTIONIST", is_active="on"))
        self.assertContains(r, "must stay Doctor")
