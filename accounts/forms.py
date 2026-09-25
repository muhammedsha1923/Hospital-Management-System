from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction

from patients.models import Patient

from .models import User


# ---- shared widgets / mixins (imported by the other apps) ----
class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%H:%M")
        super().__init__(**kwargs)


class StyledFormMixin:
    """Adds CSS classes to every widget so templates stay clean."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css = "form-check" if isinstance(widget, forms.CheckboxInput) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class LoginForm(StyledFormMixin, AuthenticationForm):
    pass


class RegistrationForm(StyledFormMixin, UserCreationForm):
    """Public self-registration. Always creates a Patient user + Patient profile."""
    date_of_birth = forms.DateField(widget=DateInput())
    gender = forms.ChoiceField(choices=Patient.Gender.choices)
    blood_group = forms.ChoiceField(choices=[("", "Unknown")] + [c for c in Patient.BloodGroup.choices], required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True

    def clean_date_of_birth(self):
        from django.utils import timezone
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PATIENT
        user.save()
        Patient.objects.create(
            user=user, first_name=user.first_name, last_name=user.last_name,
            date_of_birth=self.cleaned_data["date_of_birth"], gender=self.cleaned_data["gender"],
            blood_group=self.cleaned_data.get("blood_group", ""), phone=user.phone,
            email=user.email, address=self.cleaned_data.get("address", ""),
        )
        return user


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")


class StaffUserForm(StyledFormMixin, UserCreationForm):
    """Admin creates Administrator / Receptionist accounts. (Doctors & patients have their own forms.)"""
    role = forms.ChoiceField(choices=[(User.Role.RECEPTIONIST, "Receptionist"), (User.Role.ADMIN, "Administrator")])

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email", "phone", "role")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        if commit:
            user.save()
        return user


class UserAdminForm(StyledFormMixin, forms.ModelForm):
    """Admin edits role / active flag of an existing user."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "role", "is_active")

    def clean_role(self):
        role = self.cleaned_data["role"]
        user = self.instance
        has_doctor = hasattr(user, "doctor_profile")
        has_patient = hasattr(user, "patient_profile")
        if role == User.Role.DOCTOR and not has_doctor:
            raise forms.ValidationError("Create a doctor profile first (Doctors → Add doctor).")
        if role == User.Role.PATIENT and not has_patient:
            raise forms.ValidationError("This user has no patient profile. Register the patient first.")
        if has_doctor and role != User.Role.DOCTOR:
            raise forms.ValidationError("This user has a doctor profile, so the role must stay Doctor.")
        if has_patient and role != User.Role.PATIENT:
            raise forms.ValidationError("This user has a patient profile, so the role must stay Patient.")
        return role

    def clean_is_active(self):
        active = self.cleaned_data["is_active"]
        if not active and self.instance.pk == getattr(self, "acting_user_id", None):
            raise forms.ValidationError("You cannot deactivate your own account.")
        return active
