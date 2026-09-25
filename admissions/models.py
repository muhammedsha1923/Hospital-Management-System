from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Bed(models.Model):
    class BedType(models.TextChoices):
        GENERAL = "GENERAL", "General ward"
        SEMI = "SEMI", "Semi-private"
        PRIVATE = "PRIVATE", "Private room"
        ICU = "ICU", "ICU"

    room_number = models.CharField(max_length=20)
    bed_number = models.CharField(max_length=10, default="1")
    bed_type = models.CharField(max_length=10, choices=BedType.choices, default=BedType.GENERAL)
    department = models.ForeignKey("doctors.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="beds")
    daily_rate = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True, help_text="Untick if out of service (maintenance).")

    class Meta:
        ordering = ["room_number", "bed_number"]
        constraints = [models.UniqueConstraint(fields=["room_number", "bed_number"], name="unique_room_bed")]

    @property
    def current_admission(self):
        return self.admissions.filter(status=Admission.Status.ADMITTED).select_related("patient").first()

    @property
    def is_occupied(self):
        return self.admissions.filter(status=Admission.Status.ADMITTED).exists()

    def __str__(self):
        return f"Room {self.room_number} / Bed {self.bed_number} ({self.get_bed_type_display()})"


class Admission(models.Model):
    class Status(models.TextChoices):
        ADMITTED = "ADMITTED", "Admitted"
        DISCHARGED = "DISCHARGED", "Discharged"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="admissions")
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name="admissions")
    attending_doctor = models.ForeignKey("doctors.Doctor", on_delete=models.PROTECT, related_name="admissions")
    admitted_at = models.DateTimeField(default=timezone.now)
    discharged_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ADMITTED)
    daily_rate = models.DecimalField(max_digits=8, decimal_places=2, editable=False, default=0)
    notes = models.TextField(blank=True)
    admitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-admitted_at"]

    @property
    def nights(self):
        end = self.discharged_at or timezone.now()
        days = (timezone.localtime(end).date() - timezone.localtime(self.admitted_at).date()).days
        return max(days, 1)

    @property
    def room_charge(self):
        return self.nights * self.daily_rate

    def clean(self):
        if self.status == self.Status.ADMITTED and self.bed_id and self.patient_id:
            others = Admission.objects.filter(status=self.Status.ADMITTED).exclude(pk=self.pk)
            if others.filter(bed_id=self.bed_id).exists():
                raise ValidationError({"bed": "That bed is already occupied."})
            if others.filter(patient_id=self.patient_id).exists():
                raise ValidationError({"patient": "This patient is already admitted."})
            if not self.bed.is_active:
                raise ValidationError({"bed": "That bed is out of service."})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self._state.adding:
                self.daily_rate = self.bed.daily_rate
                Bed.objects.select_for_update().get(pk=self.bed_id)  # serialise concurrent admissions
                self.clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient.full_name} — {self.bed}"
