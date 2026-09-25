from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import ADMIN, DOCTOR, PATIENT, RECEPTIONIST, STAFF, role_required
from billing.services import sync_room_charge

from .forms import AdmissionForm, BedForm
from .models import Admission, Bed


def _admissions_for(user):
    qs = Admission.objects.select_related("patient", "bed", "attending_doctor__user")
    if user.role in STAFF:
        return qs
    if user.role == DOCTOR:
        return qs.filter(attending_doctor__user=user)
    if user.role == PATIENT:
        return qs.filter(patient__user=user)
    return qs.none()


@login_required
def admission_list(request):
    qs = _admissions_for(request.user)
    status = request.GET.get("status", "")
    if status in Admission.Status.values:
        qs = qs.filter(status=status)
    return render(request, "admissions/admission_list.html", {"admissions": qs, "status": status, "statuses": Admission.Status.choices})


@role_required(ADMIN, RECEPTIONIST)
def admit(request):
    form = AdmissionForm(request.POST or None, initial={"patient": request.GET.get("patient")})
    if request.method == "POST" and form.is_valid():
        form.instance.admitted_by = request.user
        try:
            adm = form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"{adm.patient.full_name} admitted to {adm.bed}.")
            return redirect("admissions:list")
    return render(request, "form.html", {"form": form, "title": "Admit patient", "cancel_url": reverse_lazy("admissions:list"),
                                         "submit_label": "Admit patient"})


@login_required
@require_POST
def discharge(request, pk):
    if request.user.role not in (ADMIN, RECEPTIONIST, DOCTOR):
        return redirect("dashboard:home")
    adm = get_object_or_404(_admissions_for(request.user), pk=pk, status=Admission.Status.ADMITTED)
    with transaction.atomic():
        adm.status, adm.discharged_at = Admission.Status.DISCHARGED, timezone.now()
        adm.save()
        bill = sync_room_charge(adm, request.user)
    messages.success(request, f"{adm.patient.full_name} discharged. Room charges of {adm.room_charge} were added to invoice {bill.invoice_number}.")
    return redirect("admissions:list")


# ---- beds (administrator) ----
@role_required(ADMIN, RECEPTIONIST)
def bed_list(request):
    beds = list(Bed.objects.select_related("department"))
    occupied = {a.bed_id: a for a in Admission.objects.filter(status=Admission.Status.ADMITTED).select_related("patient")}
    for b in beds:
        b.occupant = occupied.get(b.pk)
    return render(request, "admissions/bed_list.html", {"beds": beds})


@role_required(ADMIN)
def bed_create(request):
    form = BedForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bed added.")
        return redirect("admissions:beds")
    return render(request, "form.html", {"form": form, "title": "Add room / bed", "cancel_url": reverse_lazy("admissions:beds")})


@role_required(ADMIN)
def bed_edit(request, pk):
    bed = get_object_or_404(Bed, pk=pk)
    form = BedForm(request.POST or None, instance=bed)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bed updated.")
        return redirect("admissions:beds")
    return render(request, "form.html", {"form": form, "title": f"Edit {bed}", "cancel_url": reverse_lazy("admissions:beds")})


@role_required(ADMIN)
@require_POST
def bed_delete(request, pk):
    bed = get_object_or_404(Bed, pk=pk)
    try:
        bed.delete()
        messages.success(request, "Bed deleted.")
    except ProtectedError:
        messages.error(request, "This bed has admission history. Mark it inactive instead.")
    return redirect("admissions:beds")
