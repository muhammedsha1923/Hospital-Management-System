from django import forms
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from accounts.forms import StyledFormMixin, TimeInput
from accounts.models import User

from .models import Department, Doctor


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ("name", "description", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class DoctorForm(StyledFormMixin, forms.ModelForm):
    """Creates/edits the doctor profile and its login account together."""
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = Doctor
        fields = ("department", "specialization", "qualification", "license_number", "experience_years",
                  "consultation_fee", "available_from", "available_to", "is_available", "bio")
        widgets = {"available_from": TimeInput(), "available_to": TimeInput(), "bio": forms.Textarea(attrs={"rows": 3})}

    field_order = ["first_name", "last_name", "email", "phone", "username", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        if self.instance.pk:
            for name in ("username", "password1", "password2"):
                del self.fields[name]
            u = self.instance.user
            self.initial.update(first_name=u.first_name, last_name=u.last_name, email=u.email, phone=u.phone)

    @property
    def creating(self):
        return not self.instance.pk

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        qs = User.objects.filter(email__iexact=email)
        if not self.creating:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("available_from") and data.get("available_to") and data["available_to"] <= data["available_from"]:
            self.add_error("available_to", "Working hours must end after they start.")
        if self.creating:
            p1, p2 = data.get("password1"), data.get("password2")
            if p1 and p2:
                if p1 != p2:
                    self.add_error("password2", "The two passwords do not match.")
                else:
                    try:
                        validate_password(p1)
                    except forms.ValidationError as exc:
                        self.add_error("password1", exc)
        return data

    @transaction.atomic
    def save(self, commit=True):
        doctor = super().save(commit=False)
        user = doctor.user if doctor.pk else User(username=self.cleaned_data["username"], role=User.Role.DOCTOR)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        if self.creating:
            user.set_password(self.cleaned_data["password1"])
        user.save()
        doctor.user = user
        doctor.save()
        return doctor
