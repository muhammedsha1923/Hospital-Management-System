from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import ADMIN, PATIENT, RECEPTIONIST, STAFF, role_required
from doctors.models import Doctor

from .forms import AppointmentForm
from .models import Appointment
from .services import allowed_statuses, appointments_for_user, can_check_in, decorate


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@login_required
def appointment_list(request):
    qs = appointments_for_user(request.user)
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    date = request.GET.get("date", "")
    if q:
        qs = qs.filter(Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q) | Q(patient__patient_id__icontains=q)
                       | Q(doctor__user__first_name__icontains=q) | Q(doctor__user__last_name__icontains=q))
    if status in Appointment.Status.values:
        qs = qs.filter(status=status)
    if date:
        qs = qs.filter(date=date)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    page.object_list = decorate(request.user, page.object_list)
    return render(request, "appointments/list.html", {"page": page, "q": q, "status": status, "date": date,
                                                      "statuses": Appointment.Status.choices})


@login_required
def appointment_detail(request, pk):
    appt = get_object_or_404(appointments_for_user(request.user), pk=pk)
    appt = decorate(request.user, [appt])[0]
    return render(request, "appointments/detail.html", {"a": appt})


@role_required(ADMIN, RECEPTIONIST, PATIENT)
def appointment_create(request):
    user = request.user
    appt = Appointment(created_by=user)
    if user.role == PATIENT:
        if not hasattr(user, "patient_profile"):
            messages.error(request, "Your account has no patient profile yet. Please contact reception.")
            return redirect("dashboard:home")
        appt.patient, appt.status = user.patient_profile, Appointment.Status.PENDING
    initial = {}
    if request.GET.get("doctor", "").isdigit():
        doctor = Doctor.objects.filter(pk=request.GET["doctor"]).first()
        if doctor:
            initial.update(doctor=doctor, department=doctor.department)
    if request.GET.get("patient", "").isdigit():
        initial["patient"] = request.GET["patient"]
    form = AppointmentForm(request.POST or None, instance=appt, user=user, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            saved = form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if user.role == PATIENT:
                messages.success(request, "Appointment requested. You'll see it as Scheduled once the hospital confirms it.")
            else:
                messages.success(request, f"Appointment booked for {saved.patient.full_name} on {saved.date:%d %b %Y} at {saved.time:%H:%M}.")
            return redirect("appointments:detail", pk=saved.pk)
    title = "Request an appointment" if user.role == PATIENT else "Schedule appointment"
    return render(request, "appointments/form.html", {"form": form, "title": title, "cancel_url": reverse_lazy("appointments:list")})


@role_required(ADMIN, RECEPTIONIST)
def appointment_edit(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    form = AppointmentForm(request.POST or None, instance=appt, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Appointment updated.")
            return redirect("appointments:detail", pk=pk)
    return render(request, "appointments/form.html", {"form": form, "title": "Update appointment",
                                                      "cancel_url": reverse("appointments:detail", args=[pk]), "editing": appt})


def _respond(request, appt, ok, message):
    if _is_ajax(request):
        appt = decorate(request.user, [appointments_for_user(request.user).get(pk=appt.pk)])[0]
        html = render_to_string("appointments/_actions.html", {"a": appt, "next_url": request.POST.get("next", "")}, request=request)
        return JsonResponse({"ok": ok, "message": message, "status": appt.status, "label": appt.get_status_display(),
                             "checked_in": bool(appt.checked_in_at), "actions_html": html}, status=200 if ok else 400)
    (messages.success if ok else messages.error)(request, message)
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect("appointments:detail", pk=appt.pk)


@login_required
@require_POST
def appointment_status(request, pk):
    appt = get_object_or_404(appointments_for_user(request.user), pk=pk)
    new = request.POST.get("status")
    if new not in allowed_statuses(request.user, appt):
        return _respond(request, appt, False, "You can't change this appointment to that status.")
    appt.status = new
    try:
        appt.save()
    except ValidationError as exc:
        return _respond(request, appt, False, " ".join(exc.messages))
    return _respond(request, appt, True, f"Appointment marked {appt.get_status_display().lower()}.")


@role_required(ADMIN, RECEPTIONIST)
@require_POST
def appointment_checkin(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    if not can_check_in(request.user, appt):
        return _respond(request, appt, False, "Only today's scheduled appointments can be checked in.")
    appt.checked_in_at = timezone.now()
    appt.save(update_fields=["checked_in_at", "updated_at"])
    return _respond(request, appt, True, f"{appt.patient.full_name} checked in.")


@login_required
def free_slots(request):
    """JSON list of 30-minute slots for a doctor/date, marking which are free."""
    doctor = get_object_or_404(Doctor, pk=request.GET.get("doctor") or 0)
    try:
        day = datetime.strptime(request.GET.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid date"}, status=400)
    now = timezone.localtime().replace(tzinfo=None)
    booked = Appointment.objects.filter(doctor=doctor, date=day).exclude(status=Appointment.Status.CANCELLED)
    exclude = request.GET.get("exclude")
    if exclude and exclude.isdigit():
        booked = booked.exclude(pk=exclude)
    booked = list(booked)
    slots, cursor = [], datetime.combine(day, doctor.available_from)
    closing = datetime.combine(day, doctor.available_to)
    step = timedelta(minutes=30)
    while cursor + step <= closing:
        busy = any(a.start < cursor + step and a.end > cursor for a in booked)
        slots.append({"time": cursor.strftime("%H:%M"), "free": not busy and cursor > now and doctor.is_available})
        cursor += step
    return JsonResponse({"doctor": doctor.full_name, "slots": slots})
