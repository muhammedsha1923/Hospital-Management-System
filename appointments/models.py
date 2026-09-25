from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="appointments")
    doctor = models.ForeignKey("doctors.Doctor", on_delete=models.PROTECT, related_name="appointments")
    department = models.ForeignKey("doctors.Department", on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField()
    time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.TextField(blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-time"]
        indexes = [models.Index(fields=["doctor", "date"])]

    # ---- helpers ----
    @property
    def start(self):
        day, at = self.date, self.time
        if isinstance(day, str):
            day = datetime.strptime(day, "%Y-%m-%d").date()
        if isinstance(at, str):
            at = datetime.strptime(at[:5], "%H:%M").time()
        return datetime.combine(day, at)

    @property
    def end(self):
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def is_active(self):
        return self.status != self.Status.CANCELLED

    def find_conflicts(self):
        """Other non-cancelled appointments of the same doctor that overlap this one."""
        others = Appointment.objects.filter(doctor_id=self.doctor_id, date=self.date).exclude(status=self.Status.CANCELLED)
        if self.pk:
            others = others.exclude(pk=self.pk)
        return [a for a in others if a.start < self.end and a.end > self.start]

    def check_conflicts(self):
        if self.find_conflicts():
            raise ValidationError({"time": "This doctor already has an appointment at that time. Please choose another slot."})

    def clean(self):
        if not (self.doctor_id and self.date and self.time):
            return
        if self.status in (self.Status.PENDING, self.Status.SCHEDULED):
            doc = self.doctor
            if not doc.is_available:
                raise ValidationError({"doctor": f"{doc.full_name} is not accepting appointments right now."})
            opens, closes = (datetime.combine(self.start.date(), doc.available_from), datetime.combine(self.start.date(), doc.available_to))
            if self.start < opens or self.end > closes:
                raise ValidationError({"time": f"{doc.full_name} sees patients between "
                                               f"{doc.available_from:%H:%M} and {doc.available_to:%H:%M}."})
        if self.is_active:
            self.check_conflicts()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.doctor_id:
                if not self.department_id:
                    self.department_id = self.doctor.department_id
                if self.is_active:
                    # lock the doctor row so two simultaneous bookings cannot both pass the check
                    type(self.doctor).objects.select_for_update().get(pk=self.doctor_id)
                    self.check_conflicts()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient.full_name} with {self.doctor.full_name} on {self.date} {self.time:%H:%M}"
