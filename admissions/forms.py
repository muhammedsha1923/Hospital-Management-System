from django import forms

from accounts.forms import StyledFormMixin
from doctors.models import Doctor

from .models import Admission, Bed


class BedForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Bed
        fields = ("room_number", "bed_number", "bed_type", "department", "daily_rate", "is_active")


class AdmissionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Admission
        fields = ("patient", "bed", "attending_doctor", "reason", "notes")
        widgets = {"reason": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        occupied = Admission.objects.filter(status=Admission.Status.ADMITTED).values_list("bed_id", flat=True)
        self.fields["bed"].queryset = Bed.objects.filter(is_active=True).exclude(pk__in=list(occupied))
        self.fields["bed"].empty_label = "— choose a free bed —"
        self.fields["attending_doctor"].queryset = Doctor.objects.select_related("user")
        self.fields["attending_doctor"].label_from_instance = lambda d: f"{d.full_name} — {d.specialization}"
