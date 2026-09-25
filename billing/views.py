from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import ADMIN, PATIENT, RECEPTIONIST, STAFF, role_required
from admissions.models import Admission
from appointments.models import Appointment

from .forms import BillForm, PaymentForm, item_formset
from .models import Bill, BillItem


def _bills_for(user):
    qs = Bill.objects.select_related("patient").prefetch_related("items", "payments")
    if user.role in STAFF:
        return qs
    if user.role == PATIENT:
        return qs.filter(patient__user=user)
    return qs.none()  # doctors have no access to billing


@role_required(ADMIN, RECEPTIONIST, PATIENT)
def bill_list(request):
    qs = _bills_for(request.user)
    q, status = request.GET.get("q", "").strip(), request.GET.get("status", "")
    if q:
        qs = qs.filter(Q(invoice_number__icontains=q) | Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q)
                       | Q(patient__patient_id__icontains=q))
    if status in Bill.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "billing/list.html", {"page": page, "q": q, "status": status, "statuses": Bill.Status.choices})


def _prefill(request):
    """Build initial bill data from ?appointment= / ?admission= / ?patient= links."""
    initial, items = {}, []
    if request.GET.get("appointment", "").isdigit():
        appt = Appointment.objects.select_related("doctor__user", "patient").filter(pk=request.GET["appointment"]).first()
        if appt:
            initial.update(patient=appt.patient, appointment=appt)
            items.append({"category": BillItem.Category.CONSULTATION, "description": f"Consultation — {appt.doctor.full_name}",
                          "quantity": 1, "unit_price": appt.doctor.consultation_fee})
    if request.GET.get("admission", "").isdigit():
        adm = Admission.objects.select_related("patient", "bed").filter(pk=request.GET["admission"]).first()
        if adm:
            initial.update(patient=adm.patient, admission=adm)
            items.append({"category": BillItem.Category.ROOM, "description": f"{adm.bed} — {adm.nights} night(s)",
                          "quantity": adm.nights, "unit_price": adm.daily_rate})
    if request.GET.get("patient", "").isdigit():
        initial.setdefault("patient", request.GET["patient"])
    return initial, items


@role_required(ADMIN, RECEPTIONIST)
def bill_create(request):
    initial, items = _prefill(request) if request.method == "GET" else ({}, [])
    FormSet = item_formset(extra=max(1, len(items)))
    bill = Bill(created_by=request.user)
    form = BillForm(request.POST or None, instance=bill, initial=initial)
    formset = FormSet(request.POST or None, instance=bill, initial=items)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        if not any(f.cleaned_data and not f.cleaned_data.get("DELETE") for f in formset.forms):
            messages.error(request, "Add at least one line item to the bill.")
        else:
            with transaction.atomic():
                bill = form.save()
                formset.instance = bill
                formset.save()
                bill.refresh_status()
            messages.success(request, f"Invoice {bill.invoice_number} created.")
            return redirect("billing:detail", pk=bill.pk)
    return render(request, "billing/form.html", {"form": form, "formset": formset, "title": "Create bill"})


@role_required(ADMIN, RECEPTIONIST)
def bill_edit(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    FormSet = item_formset(extra=1)
    form = BillForm(request.POST or None, instance=bill)
    formset = FormSet(request.POST or None, instance=bill)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
            bill.refresh_status()
        messages.success(request, "Bill updated.")
        return redirect("billing:detail", pk=pk)
    return render(request, "billing/form.html", {"form": form, "formset": formset, "title": f"Edit {bill.invoice_number}", "bill": bill})


@role_required(ADMIN, RECEPTIONIST, PATIENT)
def bill_detail(request, pk):
    bill = get_object_or_404(_bills_for(request.user), pk=pk)
    ctx = {"bill": bill, "can_manage": request.user.role in STAFF}
    if ctx["can_manage"] and bill.balance > 0:
        ctx["payment_form"] = PaymentForm(bill=bill, initial={"amount": bill.balance})
    return render(request, "billing/detail.html", ctx)


@role_required(ADMIN, RECEPTIONIST, PATIENT)
def bill_print(request, pk):
    bill = get_object_or_404(_bills_for(request.user), pk=pk)
    return render(request, "billing/print.html", {"bill": bill})


@role_required(ADMIN, RECEPTIONIST)
@require_POST
def add_payment(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    form = PaymentForm(request.POST, bill=bill)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.bill, payment.received_by = bill, request.user
        payment.save()
        bill.refresh_from_db()
        messages.success(request, f"Payment of {payment.amount} recorded. Invoice is now {bill.get_status_display().lower()}.")
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("billing:detail", pk=pk)


@role_required(ADMIN)
@require_POST
def bill_delete(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    if bill.payments.exists():
        messages.error(request, "Bills with recorded payments cannot be deleted.")
        return redirect("billing:detail", pk=pk)
    bill.delete()
    messages.success(request, "Bill deleted.")
    return redirect("billing:list")
