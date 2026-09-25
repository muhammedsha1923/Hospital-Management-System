from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .decorators import ADMIN, role_required
from .forms import LoginForm, ProfileForm, RegistrationForm, StaffUserForm, UserAdminForm
from .models import User


class HospitalLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your patient account has been created. Welcome!")
        return redirect("dashboard:home")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


class ChangePasswordView(SuccessMessageMixin, PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")
    success_message = "Your password has been changed."


# ---------------- administrator: user & role management ----------------
@role_required(ADMIN)
def user_list(request):
    qs = User.objects.all().order_by("role", "username")
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if role:
        qs = qs.filter(role=role)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "accounts/user_list.html", {"page": page, "q": q, "role": role, "roles": User.Role.choices})


@role_required(ADMIN)
def user_create(request):
    form = StaffUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Account '{user.username}' created as {user.get_role_display()}.")
        return redirect("accounts:user_list")
    return render(request, "form.html", {"form": form, "title": "Add staff account",
                                         "subtitle": "Create an administrator or receptionist login. Doctors and patients are added from their own sections.",
                                         "cancel_url": reverse_lazy("accounts:user_list")})


@role_required(ADMIN)
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserAdminForm(request.POST or None, instance=user)
    form.acting_user_id = request.user.pk
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Access for '{user.username}' updated.")
        return redirect("accounts:user_list")
    return render(request, "form.html", {"form": form, "title": f"Manage access: {user.username}",
                                         "cancel_url": reverse_lazy("accounts:user_list")})


@role_required(ADMIN)
@require_POST
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        messages.success(request, f"'{user.username}' is now {'active' if user.is_active else 'deactivated'}.")
    return redirect("accounts:user_list")
