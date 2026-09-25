from django import forms
from django.forms import inlineformset_factory

from accounts.forms import DateInput, StyledFormMixin

from .models import MedicalRecord, Prescription


class MedicalRecordForm(StyledFormMixin, forms.ModelForm):
    mark_completed = forms.BooleanField(required=False, initial=True, label="Mark the linked appointment as completed")

    class Meta:
        model = MedicalRecord
        fields = ("visit_date", "symptoms", "diagnosis", "treatment", "notes", "follow_up_date")
        widgets = {"visit_date": DateInput(), "follow_up_date": DateInput(),
                   "symptoms": forms.Textarea(attrs={"rows": 2}), "diagnosis": forms.Textarea(attrs={"rows": 3}),
                   "treatment": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, show_complete=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not show_complete:
            del self.fields["mark_completed"]

    def clean(self):
        data = super().clean()
        visit, follow = data.get("visit_date"), data.get("follow_up_date")
        if visit and follow and follow < visit:
            self.add_error("follow_up_date", "The follow-up date cannot be before the visit date.")
        return data


class PrescriptionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ("medication", "dosage", "frequency", "duration", "instructions")


PrescriptionFormSet = inlineformset_factory(MedicalRecord, Prescription, form=PrescriptionForm, extra=1, can_delete=True)
