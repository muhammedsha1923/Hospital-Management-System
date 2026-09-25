from django.utils import timezone

from accounts.decorators import ADMIN, DOCTOR, PATIENT, RECEPTIONIST

from .models import Appointment

S = Appointment.Status
ACTION_LABELS = {S.SCHEDULED: ("Confirm", "btn-primary"), S.COMPLETED: ("Complete", "btn-success"),
                 S.CANCELLED: ("Cancel", "btn-danger"), S.PENDING: ("Set pending", "btn-outline")}


def allowed_statuses(user, appt):
    """Status values `user` may move `appt` to."""
    cur, role = appt.status, user.role
    if role == ADMIN:
        return [s for s in S.values if s != cur]
    if role == RECEPTIONIST:
        return [] if cur == S.COMPLETED else [s for s in (S.SCHEDULED, S.CANCELLED) if s != cur]
    if role == DOCTOR and appt.doctor.user_id == user.id:
        return {S.PENDING: [S.SCHEDULED, S.CANCELLED], S.SCHEDULED: [S.COMPLETED, S.CANCELLED]}.get(cur, [])
    if role == PATIENT and appt.patient.user_id == user.id:
        return [S.CANCELLED] if cur in (S.PENDING, S.SCHEDULED) else []
    return []


def can_check_in(user, appt):
    return (user.role in (ADMIN, RECEPTIONIST) and appt.status == S.SCHEDULED
            and appt.date == timezone.localdate() and not appt.checked_in_at)


def decorate(user, appointments):
    """Attach `.actions` and `.can_checkin` so templates can render buttons without logic."""
    appointments = list(appointments)
    for a in appointments:
        a.actions = [(v, *ACTION_LABELS[v]) for v in allowed_statuses(user, a)]
        a.can_checkin = can_check_in(user, a)
    return appointments


def appointments_for_user(user):
    qs = Appointment.objects.select_related("patient", "doctor__user", "department")
    if user.role in (ADMIN, RECEPTIONIST):
        return qs
    if user.role == DOCTOR:
        return qs.filter(doctor__user=user)
    if user.role == PATIENT:
        return qs.filter(patient__user=user)
    return qs.none()
