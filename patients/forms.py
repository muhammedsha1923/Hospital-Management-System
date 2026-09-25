from django import forms
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from accounts.forms import DateInput, StyledFormMixin
from accounts.models import User

from .models import Patient


class PatientForm(StyledFormMixin, forms.ModelForm):
    """Used by reception/admin. On creation it can optionally create a patient portal login."""
    create_account = forms.BooleanField(required=False, label="Create a patient portal login")
    username = forms.CharField(max_length=150, required=False)
    password1 = forms.CharField(label="Temporary password", widget=forms.PasswordInput, required=False)

    class Meta:
        model = Patient
        exclude = ("user", "patient_id", "registered_by")
        widgets = {
            "date_of_birth": DateInput(),
            "address": forms.Textarea(attrs={"rows": 2}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
            "medical_history": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.acting_user = kwargs.pop("acting_user", None)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            for name in ("create_account", "username", "password1"):
                del self.fields[name]
        if self.acting_user is not None and self.acting_user.role == User.Role.RECEPTIONIST:
            # clinical history is the doctors' domain
            self.fields.pop("medical_history", None)

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob

    def clean(self):
        data = super().clean()
        if data.get("create_account"):
            username, pw = data.get("username"), data.get("password1")
            if not username:
                self.add_error("username", "Enter a username for the portal login.")
            elif User.objects.filter(username__iexact=username).exists():
                self.add_error("username", "This username is already taken.")
            if not pw:
                self.add_error("password1", "Enter a temporary password.")
            else:
                try:
                    validate_password(pw)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return data

    @transaction.atomic
    def save(self, commit=True):
        patient = super().save(commit=False)
        creating = patient.pk is None
        if creating:
            patient.registered_by = self.acting_user
            if self.cleaned_data.get("create_account"):
                user = User(username=self.cleaned_data["username"], first_name=patient.first_name,
                            last_name=patient.last_name, email=patient.email, phone=patient.phone,
                            role=User.Role.PATIENT)
                user.set_password(self.cleaned_data["password1"])
                user.save()
                patient.user = user
        patient.save()
        return patient


class PatientSelfForm(StyledFormMixin, forms.ModelForm):
    """What a patient may change about their own profile."""

    class Meta:
        model = Patient
        fields = ("phone", "email", "address", "emergency_contact_name", "emergency_contact_phone",
                  "emergency_contact_relation", "allergies")
        widgets = {"address": forms.Textarea(attrs={"rows": 2}), "allergies": forms.Textarea(attrs={"rows": 2})}
