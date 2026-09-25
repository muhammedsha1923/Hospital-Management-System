"""Create demo departments, users, appointments, a bed and a bill for trying the system out."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from admissions.models import Bed
from appointments.models import Appointment
from billing.models import Bill, BillItem, Payment
from doctors.models import Department, Doctor
from patients.models import Patient
from records.models import MedicalRecord, Prescription

PASSWORD = "Hospital@123"


class Command(BaseCommand):
    help = "Load demo data (development only)."

    def handle(self, *args, **opts):
        def user(username, role, first, last, **extra):
            u, created = User.objects.get_or_create(username=username, defaults=dict(role=role, first_name=first, last_name=last, email=f"{username}@example.com", **extra))
            if created:
                u.set_password(PASSWORD)
                u.save()
            return u

        user("admin", User.Role.ADMIN, "Alex", "Admin", is_staff=True, is_superuser=True)
        user("reception", User.Role.RECEPTIONIST, "Riya", "Reception")
        depts = {n: Department.objects.get_or_create(name=n)[0] for n in ("Cardiology", "Pediatrics", "Orthopedics", "General Medicine")}
        docs = []
        for i, (uname, first, last, dept, spec, fee) in enumerate([
            ("dr.rao", "Meera", "Rao", "Cardiology", "Cardiologist", 800),
            ("dr.khan", "Imran", "Khan", "Pediatrics", "Pediatrician", 600),
            ("dr.nair", "Anil", "Nair", "General Medicine", "General Physician", 400)]):
            u = user(uname, User.Role.DOCTOR, first, last)
            d, _ = Doctor.objects.get_or_create(user=u, defaults=dict(department=depts[dept], specialization=spec, license_number=f"LIC-{1000+i}",
                                                                      qualification="MD", experience_years=8 + i, consultation_fee=fee))
            docs.append(d)
        pu = user("patient1", User.Role.PATIENT, "Sam", "Patel")
        p1, _ = Patient.objects.get_or_create(user=pu, defaults=dict(first_name="Sam", last_name="Patel", date_of_birth="1990-04-12", gender="M",
                                                                     blood_group="O+", phone="9000000001", email=pu.email, allergies="Penicillin",
                                                                     emergency_contact_name="Nita Patel", emergency_contact_phone="9000000002",
                                                                     emergency_contact_relation="Spouse", medical_history="Mild asthma"))
        p2, _ = Patient.objects.get_or_create(first_name="Lena", last_name="Fernandes", defaults=dict(date_of_birth="1978-09-30", gender="F", blood_group="A+", phone="9000000003"))
        for n, (room, bed_type, rate) in enumerate([("101", "GENERAL", 1200), ("102", "PRIVATE", 3500), ("ICU-1", "ICU", 8000)]):
            Bed.objects.get_or_create(room_number=room, bed_number="1", defaults=dict(bed_type=bed_type, daily_rate=rate))
        tomorrow = timezone.localdate() + timedelta(days=1)
        if not Appointment.objects.exists():
            a1 = Appointment.objects.create(patient=p1, doctor=docs[0], department=docs[0].department, date=tomorrow, time="10:00", reason="Chest discomfort", status="SCHEDULED")
            Appointment.objects.create(patient=p2, doctor=docs[2], department=docs[2].department, date=tomorrow, time="11:00", reason="Fever and cough", status="PENDING")
            past = Appointment.objects.create(patient=p1, doctor=docs[2], department=docs[2].department, date=timezone.localdate() - timedelta(days=7), time="09:30", reason="Annual check-up", status="COMPLETED")
            rec = MedicalRecord.objects.create(patient=p1, doctor=docs[2], appointment=past, diagnosis="Seasonal allergic rhinitis", treatment="Antihistamines", follow_up_date=tomorrow + timedelta(days=14))
            Prescription.objects.create(record=rec, medication="Cetirizine", dosage="10 mg", frequency="Once daily", duration="7 days")
            bill = Bill.objects.create(patient=p1, appointment=past)
            BillItem.objects.create(bill=bill, category="CONSULTATION", description="Consultation — General Medicine", quantity=1, unit_price=400)
            BillItem.objects.create(bill=bill, category="MEDICINE", description="Cetirizine 10 mg x7", quantity=7, unit_price=5)
            Payment.objects.create(bill=bill, amount=200, method="CASH")
        self.stdout.write(self.style.SUCCESS(f"Demo data ready. Logins (password '{PASSWORD}'): admin, reception, dr.rao, dr.khan, dr.nair, patient1"))
