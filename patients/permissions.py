"""Central place that decides which patients a user may see. Every patient/record view goes through it."""
from django.db.models import Q

from .models import Patient

CONFIRMED = ["SCHEDULED", "COMPLETED"]


def patients_for_user(user):
    role = user.role
    if role in ("ADMIN", "RECEPTIONIST"):
        return Patient.objects.all()
    if role == "DOCTOR":
        doctor = getattr(user, "doctor_profile", None)
        if doctor is None:
            return Patient.objects.none()
        # "Assigned" = confirmed/completed appointment, a record they wrote, or an admission under their care.
        return Patient.objects.filter(
            Q(appointments__doctor=doctor, appointments__status__in=CONFIRMED)
            | Q(records__doctor=doctor)
            | Q(admissions__attending_doctor=doctor)
        ).distinct()
    if role == "PATIENT":
        return Patient.objects.filter(user=user)
    return Patient.objects.none()


def can_view_clinical(user):
    """Diagnoses, prescriptions and medical history are hidden from reception staff."""
    return user.role in ("ADMIN", "DOCTOR", "PATIENT")
