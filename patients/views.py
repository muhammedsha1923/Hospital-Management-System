from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from accounts.decorators import ADMIN, DOCTOR, PATIENT, RECEPTIONIST, STAFF, role_required

from .forms import PatientForm, PatientSelfForm
from .permissions import can_view_clinical, patients_for_user


@role_required(ADMIN, RECEPTIONIST, DOCTOR)
def patient_list(request):
    qs = patients_for_user(request.user)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(patient_id__icontains=q)
                       | Q(phone__icontains=q) | Q(email__icontains=q))
    page = Paginator(qs.order_by("first_name", "last_name"), 15).get_page(request.GET.get("page"))
    return render(request, "patients/list.html", {"page": page, "q": q})


@role_required(ADMIN, RECEPTIONIST)
def patient_create(request):
    form = PatientForm(request.POST or None, acting_user=request.user)
    if request.method == "POST" and form.is_valid():
        patient = form.save()
        messages.success(request, f"{patient.full_name} registered with ID {patient.patient_id}.")
        return redirect("patients:detail", pk=patient.pk)
    return render(request, "form.html", {"form": form, "title": "Register patient", "cancel_url": reverse_lazy("patients:list")})


@login_required
def patient_detail(request, pk):
    patient = get_object_or_404(patients_for_user(request.user), pk=pk)
    role = request.user.role
    ctx = {"patient": patient, "clinical": can_view_clinical(request.user)}
    appts = patient.appointments.select_related("doctor__user", "department")
    if role == DOCTOR:
        appts = appts.filter(doctor__user=request.user)
    ctx["appointments"] = appts[:10]
    ctx["admissions"] = patient.admissions.select_related("bed", "attending_doctor__user")[:10]
    if ctx["clinical"]:
        ctx["records"] = patient.records.select_related("doctor__user").prefetch_related("prescriptions")
    if role != DOCTOR:
        ctx["bills"] = patient.bills.prefetch_related("items", "payments")[:10]
    return render(request, "patients/detail.html", ctx)


@login_required
def my_profile(request):
    if request.user.role != PATIENT or not hasattr(request.user, "patient_profile"):
        return redirect("dashboard:home")
    return redirect("patients:detail", pk=request.user.patient_profile.pk)


@login_required
def patient_edit(request, pk):
    patient = get_object_or_404(patients_for_user(request.user), pk=pk)
    if request.user.role == PATIENT:
        form = PatientSelfForm(request.POST or None, instance=patient)
    elif request.user.role in STAFF:
        form = PatientForm(request.POST or None, instance=patient, acting_user=request.user)
    else:
        return redirect("patients:detail", pk=pk)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Patient details updated.")
        return redirect("patients:detail", pk=pk)
    return render(request, "form.html", {"form": form, "title": f"Edit {patient.full_name}",
                                         "cancel_url": reverse("patients:detail", args=[pk])})


@role_required(ADMIN)
@require_POST
def patient_delete(request, pk):
    patient = get_object_or_404(patients_for_user(request.user), pk=pk)
    try:
        patient.delete()
        messages.success(request, "Patient deleted.")
    except ProtectedError:
        messages.error(request, "This patient has appointments, admissions or bills and cannot be deleted.")
        return redirect("patients:detail", pk=pk)
    return redirect("patients:list")
