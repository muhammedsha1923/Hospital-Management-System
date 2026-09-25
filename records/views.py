from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import ADMIN, DOCTOR, PATIENT, role_required
from appointments.models import Appointment
from patients.permissions import patients_for_user

from .forms import MedicalRecordForm, PrescriptionFormSet
from .models import MedicalRecord, Prescription


def _visible_records(user):
    """Reception staff never see clinical data; everyone else follows patient visibility."""
    if user.role not in (ADMIN, DOCTOR, PATIENT):
        return MedicalRecord.objects.none()
    return MedicalRecord.objects.filter(patient__in=patients_for_user(user))


@role_required(DOCTOR)
def record_create(request, patient_pk):
    patient = get_object_or_404(patients_for_user(request.user), pk=patient_pk)
    doctor = request.user.doctor_profile
    appt = None
    if request.GET.get("appointment", "").isdigit():
        appt = get_object_or_404(Appointment, pk=request.GET["appointment"], doctor=doctor, patient=patient)
    record = MedicalRecord(patient=patient, doctor=doctor, appointment=appt)
    if appt:
        record.visit_date = appt.date
    show_complete = bool(appt and appt.status == Appointment.Status.SCHEDULED)
    form = MedicalRecordForm(request.POST or None, instance=record, show_complete=show_complete)
    formset = PrescriptionFormSet(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            record = form.save()
            formset.instance = record
            formset.save()
            if show_complete and form.cleaned_data.get("mark_completed"):
                appt.status = Appointment.Status.COMPLETED
                appt.save()
        messages.success(request, "Medical record saved.")
        return redirect("records:detail", pk=record.pk)
    return render(request, "records/form.html", {"form": form, "formset": formset, "patient": patient, "title": "New medical record"})


@role_required(DOCTOR)
def record_edit(request, pk):
    record = get_object_or_404(MedicalRecord, pk=pk, doctor__user=request.user)  # authors only
    get_object_or_404(patients_for_user(request.user), pk=record.patient_id)
    form = MedicalRecordForm(request.POST or None, instance=record)
    formset = PrescriptionFormSet(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
        messages.success(request, "Medical record updated.")
        return redirect("records:detail", pk=pk)
    return render(request, "records/form.html", {"form": form, "formset": formset, "patient": record.patient, "title": "Edit medical record"})


@login_required
def record_detail(request, pk):
    record = get_object_or_404(_visible_records(request.user).select_related("patient", "doctor__user", "appointment").prefetch_related("prescriptions"), pk=pk)
    return render(request, "records/detail.html", {"record": record})


@role_required(PATIENT)
def my_records(request):
    patient = getattr(request.user, "patient_profile", None)
    records = _visible_records(request.user).select_related("doctor__user").prefetch_related("prescriptions")
    return render(request, "records/mine.html", {"records": records, "patient": patient})
