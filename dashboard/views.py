from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import ADMIN, DOCTOR, PATIENT, RECEPTIONIST, STAFF, role_required
from admissions.models import Admission, Bed
from appointments.models import Appointment
from appointments.services import decorate
from billing.models import Bill, Payment
from doctors.models import Doctor
from patients.models import Patient
from records.models import MedicalRecord

ZERO = 0


def _month_start(d, back):
    """First day of the month `back` months before d's month."""
    m = d.month - 1 - back
    return date(d.year + m // 12, m % 12 + 1, 1)


@login_required
def home(request):
    handler = {ADMIN: admin_dashboard, DOCTOR: doctor_dashboard, RECEPTIONIST: reception_dashboard,
               PATIENT: patient_dashboard}.get(request.user.role)
    return handler(request)


def admin_dashboard(request):
    today = timezone.localdate()
    revenue = Payment.objects.aggregate(t=Sum("amount"))["t"] or ZERO
    unpaid = sum((b.balance for b in Bill.objects.exclude(status=Bill.Status.PAID).prefetch_related("items", "payments")), ZERO)
    months = []
    for back in range(5, -1, -1):
        start = _month_start(today, back)
        end = _month_start(today, back - 1)  # first day of the following month
        total = Payment.objects.filter(paid_on__gte=start, paid_on__lt=end).aggregate(t=Sum("amount"))["t"] or ZERO
        months.append({"label": start.strftime("%b"), "total": total})
    peak = max((m["total"] for m in months), default=0) or 1
    for m in months:
        m["pct"] = round(m["total"] * 100 / peak)
    total_beds = Bed.objects.filter(is_active=True).count()
    occupied = Admission.objects.filter(status=Admission.Status.ADMITTED).count()
    ctx = {
        "stats": {"patients": Patient.objects.count(), "doctors": Doctor.objects.count(),
                  "appointments": Appointment.objects.count(), "today_appts": Appointment.objects.filter(date=today).exclude(status="CANCELLED").count(),
                  "admitted": occupied, "total_admissions": Admission.objects.count(), "revenue": revenue, "unpaid": unpaid,
                  "beds_free": max(total_beds - occupied, 0), "beds_total": total_beds},
        "months": months,
        "recent_appts": decorate(request.user, Appointment.objects.select_related("patient", "doctor__user", "department")[:6]),
        "recent_bills": Bill.objects.select_related("patient").prefetch_related("items", "payments")[:6],
    }
    return render(request, "dashboard/admin.html", ctx)


def doctor_dashboard(request):
    doctor = getattr(request.user, "doctor_profile", None)
    if doctor is None:
        return render(request, "dashboard/doctor.html", {"doctor": None})
    today = timezone.localdate()
    appts = Appointment.objects.filter(doctor=doctor).select_related("patient", "department")
    ctx = {
        "doctor": doctor,
        "today_appts": decorate(request.user, appts.filter(date=today).exclude(status="CANCELLED").order_by("time")),
        "upcoming": decorate(request.user, appts.filter(date__gt=today, status__in=["PENDING", "SCHEDULED"]).order_by("date", "time")[:6]),
        "pending_requests": appts.filter(status="PENDING").count(),
        "patient_count": Patient.objects.filter(Q(appointments__doctor=doctor, appointments__status__in=["SCHEDULED", "COMPLETED"]) | Q(records__doctor=doctor)).distinct().count(),
        "follow_ups": MedicalRecord.objects.filter(doctor=doctor, follow_up_date__gte=today).select_related("patient").order_by("follow_up_date")[:6],
        "admitted": Admission.objects.filter(attending_doctor=doctor, status="ADMITTED").select_related("patient", "bed"),
    }
    return render(request, "dashboard/doctor.html", ctx)


def reception_dashboard(request):
    today = timezone.localdate()
    todays = Appointment.objects.filter(date=today).exclude(status="CANCELLED").select_related("patient", "doctor__user", "department").order_by("time")
    occupied = Admission.objects.filter(status="ADMITTED").count()
    ctx = {
        "today_appts": decorate(request.user, todays),
        "pending": decorate(request.user, Appointment.objects.filter(status="PENDING").select_related("patient", "doctor__user", "department").order_by("date", "time")[:8]),
        "pending_count": Appointment.objects.filter(status="PENDING").count(),
        "checked_in": todays.filter(checked_in_at__isnull=False).count(),
        "admitted": occupied,
        "beds_free": max(Bed.objects.filter(is_active=True).count() - occupied, 0),
        "patients_total": Patient.objects.count(),
    }
    return render(request, "dashboard/receptionist.html", ctx)


def patient_dashboard(request):
    patient = getattr(request.user, "patient_profile", None)
    if patient is None:
        return render(request, "dashboard/patient.html", {"patient": None})
    today = timezone.localdate()
    bills = list(patient.bills.exclude(status="PAID").prefetch_related("items", "payments"))
    ctx = {
        "patient": patient,
        "upcoming": decorate(request.user, patient.appointments.filter(date__gte=today, status__in=["PENDING", "SCHEDULED"]).select_related("doctor__user", "department").order_by("date", "time")[:5]),
        "prescriptions": [p for r in patient.records.prefetch_related("prescriptions")[:3] for p in r.prescriptions.all()][:5],
        "follow_up": patient.records.filter(follow_up_date__gte=today).order_by("follow_up_date").first(),
        "unpaid_total": sum((b.balance for b in bills), ZERO),
        "unpaid_count": len(bills),
        "admission": patient.admissions.filter(status="ADMITTED").select_related("bed").first(),
        "records_count": patient.records.count(),
    }
    return render(request, "dashboard/patient.html", ctx)


@role_required(ADMIN, RECEPTIONIST)
def search(request):
    q = request.GET.get("q", "").strip()
    patients = doctors = []
    if q:
        patients = Patient.objects.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(patient_id__icontains=q)
                                          | Q(phone__icontains=q) | Q(email__icontains=q))[:20]
        doctors = Doctor.objects.select_related("user", "department").filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(specialization__icontains=q)
            | Q(department__name__icontains=q))[:20]
    return render(request, "dashboard/search.html", {"q": q, "patients": patients, "doctors": doctors})
