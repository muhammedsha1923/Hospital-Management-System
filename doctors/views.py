from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from accounts.decorators import ADMIN, PATIENT, role_required

from .forms import DepartmentForm, DoctorForm
from .models import Department, Doctor


@login_required
def doctor_list(request):
    qs = Doctor.objects.select_related("user", "department")
    q = request.GET.get("q", "").strip()
    dept = request.GET.get("department", "")
    if request.user.role == PATIENT:
        qs = qs.filter(is_available=True)
    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(specialization__icontains=q))
    if dept.isdigit():
        qs = qs.filter(department_id=dept)
    return render(request, "doctors/list.html", {"doctors": qs, "departments": Department.objects.filter(is_active=True), "q": q, "dept": dept})


@login_required
def doctor_detail(request, pk):
    doctor = get_object_or_404(Doctor.objects.select_related("user", "department"), pk=pk)
    return render(request, "doctors/detail.html", {"doctor": doctor})


@role_required(ADMIN)
def doctor_create(request):
    form = DoctorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        doctor = form.save()
        messages.success(request, f"{doctor.full_name} was added and can now sign in.")
        return redirect("doctors:detail", pk=doctor.pk)
    return render(request, "form.html", {"form": form, "title": "Add doctor", "cancel_url": reverse_lazy("doctors:list"),
                                         "subtitle": "This also creates the doctor's login account."})


@role_required(ADMIN)
def doctor_edit(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    form = DoctorForm(request.POST or None, instance=doctor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Doctor details updated.")
        return redirect("doctors:detail", pk=doctor.pk)
    return render(request, "form.html", {"form": form, "title": f"Edit {doctor.full_name}", "cancel_url": reverse_lazy("doctors:list")})


@role_required(ADMIN)
@require_POST
def doctor_delete(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    try:
        doctor.user.delete()  # cascades to the Doctor row
        messages.success(request, "Doctor removed.")
    except ProtectedError:
        messages.error(request, "This doctor has appointments or admissions on record and cannot be deleted. "
                                "Untick 'Available' or deactivate the account instead.")
        return redirect("doctors:detail", pk=pk)
    return redirect("doctors:list")


# ---- departments ----
@role_required(ADMIN)
def department_list(request):
    return render(request, "doctors/department_list.html", {"departments": Department.objects.prefetch_related("doctors")})


@role_required(ADMIN)
def department_create(request):
    form = DepartmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department created.")
        return redirect("doctors:departments")
    return render(request, "form.html", {"form": form, "title": "Add department", "cancel_url": reverse_lazy("doctors:departments")})


@role_required(ADMIN)
def department_edit(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=dept)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department updated.")
        return redirect("doctors:departments")
    return render(request, "form.html", {"form": form, "title": f"Edit {dept.name}", "cancel_url": reverse_lazy("doctors:departments")})


@role_required(ADMIN)
@require_POST
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    try:
        dept.delete()
        messages.success(request, "Department deleted.")
    except ProtectedError:
        messages.error(request, "This department still has doctors or appointments. Deactivate it instead.")
    return redirect("doctors:departments")
