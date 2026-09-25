from django import forms
from django.forms import inlineformset_factory

from accounts.forms import DateInput, StyledFormMixin
from appointments.models import Appointment

from .models import Bill, BillItem, Payment


class BillForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Bill
        fields = ("patient", "appointment", "admission", "issued_date", "due_date", "discount", "notes")
        widgets = {"issued_date": DateInput(), "due_date": DateInput(), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["appointment"].queryset = Appointment.objects.select_related("patient").exclude(status="CANCELLED")
        self.fields["appointment"].required = False
        self.fields["admission"].required = False
        self.fields["appointment"].label_from_instance = lambda a: f"{a.patient.full_name} — {a.date:%d %b %Y} {a.time:%H:%M}"

    def clean_discount(self):
        d = self.cleaned_data["discount"]
        if d < 0:
            raise forms.ValidationError("Discount cannot be negative.")
        return d

    def clean(self):
        data = super().clean()
        patient = data.get("patient")
        for key in ("appointment", "admission"):
            obj = data.get(key)
            if patient and obj and obj.patient_id != patient.pk:
                self.add_error(key, "This does not belong to the selected patient.")
        due, issued = data.get("due_date"), data.get("issued_date")
        if due and issued and due < issued:
            self.add_error("due_date", "Due date cannot be before the issue date.")
        return data


class BillItemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BillItem
        fields = ("category", "description", "quantity", "unit_price")

    def clean_unit_price(self):
        p = self.cleaned_data["unit_price"]
        if p < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return p

    def clean_quantity(self):
        q = self.cleaned_data["quantity"]
        if q < 1:
            raise forms.ValidationError("Quantity must be at least 1.")
        return q


def item_formset(extra=1):
    return inlineformset_factory(Bill, BillItem, form=BillItemForm, extra=extra, can_delete=True)


class PaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("amount", "method", "paid_on", "reference")
        widgets = {"paid_on": DateInput()}

    def __init__(self, *args, bill=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bill = bill

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Enter an amount greater than zero.")
        if self.bill is not None and amount > self.bill.balance:
            raise forms.ValidationError(f"Amount exceeds the outstanding balance of {self.bill.balance}.")
        return amount
