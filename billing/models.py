from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

ZERO = Decimal("0.00")


class Bill(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIAL = "PARTIAL", "Partially Paid"
        PAID = "PAID", "Paid"

    invoice_number = models.CharField(max_length=14, unique=True, null=True, blank=True, editable=False)
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="bills")
    appointment = models.ForeignKey("appointments.Appointment", on_delete=models.SET_NULL, null=True, blank=True, related_name="bills")
    admission = models.ForeignKey("admissions.Admission", on_delete=models.SET_NULL, null=True, blank=True, related_name="bills")
    issued_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_date", "-id"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.invoice_number:
            self.invoice_number = f"INV-{self.pk:06d}"
            Bill.objects.filter(pk=self.pk).update(invoice_number=self.invoice_number)

    # Display properties use .all() so prefetch_related('items', 'payments') avoids extra queries.
    @property
    def subtotal(self):
        return sum((i.total for i in self.items.all()), ZERO)

    @property
    def total(self):
        return max(self.subtotal - (self.discount or ZERO), ZERO)

    @property
    def amount_paid(self):
        return sum((p.amount for p in self.payments.all()), ZERO)

    @property
    def balance(self):
        return max(self.total - self.amount_paid, ZERO)

    def refresh_status(self):
        """Recompute the stored status straight from the database (called by signals)."""
        line = ExpressionWrapper(F("quantity") * F("unit_price"), output_field=DecimalField(max_digits=14, decimal_places=2))
        sub = self.items.aggregate(t=Sum(line))["t"] or ZERO
        total = max(sub - (self.discount or ZERO), ZERO)
        paid = self.payments.aggregate(t=Sum("amount"))["t"] or ZERO
        if total > 0 and paid >= total:
            status = self.Status.PAID
        elif paid > 0:
            status = self.Status.PARTIAL
        else:
            status = self.Status.PENDING
        Bill.objects.filter(pk=self.pk).update(status=status)  # safe even while the bill is being deleted
        self.status = status

    def __str__(self):
        return f"{self.invoice_number} — {self.patient.full_name}"


class BillItem(models.Model):
    class Category(models.TextChoices):
        CONSULTATION = "CONSULTATION", "Consultation"
        TREATMENT = "TREATMENT", "Treatment / procedure"
        ROOM = "ROOM", "Room charges"
        LAB = "LAB", "Laboratory test"
        MEDICINE = "MEDICINE", "Medicine"
        OTHER = "OTHER", "Other"

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="items")
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.CONSULTATION)
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total(self):
        return (self.quantity or 0) * (self.unit_price or ZERO)

    def __str__(self):
        return f"{self.description} x{self.quantity}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        CARD = "CARD", "Card"
        UPI = "UPI", "UPI / mobile wallet"
        BANK = "BANK", "Bank transfer"
        INSURANCE = "INSURANCE", "Insurance"

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
    paid_on = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=100, blank=True, help_text="Receipt / transaction number")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-id"]

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Enter an amount greater than zero."})

    def __str__(self):
        return f"{self.amount} on {self.paid_on} ({self.get_method_display()})"
