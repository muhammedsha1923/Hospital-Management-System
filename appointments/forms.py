from django import forms
from django.utils import timezone

from accounts.decorators import PATIENT
from accounts.forms import DateInput, StyledFormMixin, TimeInput
from doctors.models import Department, Doctor

from .models import Appointment


class DoctorSelect(forms.Select):
    """Adds data-department to every <option> so JavaScript can filter doctors by department."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-department"] = instance.department_id
        return option


class AppointmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ("patient", "department", "doctor", "date", "time", "reason", "status", "notes")
        widgets = {"date": DateInput(), "time": TimeInput(attrs={"step": 900}), "doctor": DoctorSelect(),
                   "reason": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        doctors = Doctor.objects.filter(is_available=True)
        if self.instance.pk:  # keep current doctor selectable even if now unavailable
            doctors = Doctor.objects.filter(pk__in=list(doctors.values_list("pk", flat=True)) + [self.instance.doctor_id])
        self.fields["doctor"].queryset = doctors.select_related("user", "department")
        self.fields["doctor"].label_from_instance = lambda d: f"{d.full_name} — {d.specialization}"
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()
        if user is not None and user.role == PATIENT:
            for name in ("patient", "status", "notes"):
                del self.fields[name]

    def clean(self):
        data = super().clean()
        doctor, dept, date, time = (data.get(k) for k in ("doctor", "department", "date", "time"))
        if doctor and dept and doctor.department_id != dept.id:
            self.add_error("doctor", f"{doctor.full_name} does not work in {dept.name}.")
        status = data.get("status") or self.instance.status
        moved = not self.instance.pk or "date" in self.changed_data or "time" in self.changed_data
        if date and time and moved and status in ("PENDING", "SCHEDULED"):
            now = timezone.localtime()
            if date < now.date() or (date == now.date() and time <= now.time()):
                self.add_error("date", "Appointments must be in the future.")
        return data
