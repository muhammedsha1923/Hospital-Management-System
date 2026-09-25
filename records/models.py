from django.db import models
from django.utils import timezone


class MedicalRecord(models.Model):
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="records")
    doctor = models.ForeignKey("doctors.Doctor", on_delete=models.PROTECT, related_name="records")
    appointment = models.ForeignKey("appointments.Appointment", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="records")
    visit_date = models.DateField(default=timezone.localdate)
    symptoms = models.TextField(blank=True)
    diagnosis = models.TextField()
    treatment = models.TextField(blank=True, help_text="Procedures, therapy or treatment plan")
    notes = models.TextField(blank=True, help_text="Treatment / progress notes")
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-visit_date", "-created_at"]

    def __str__(self):
        return f"{self.patient.full_name} — {self.visit_date}"


class Prescription(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name="prescriptions")
    medication = models.CharField(max_length=150)
    dosage = models.CharField(max_length=80, help_text="e.g. 500 mg")
    frequency = models.CharField(max_length=80, help_text="e.g. twice daily")
    duration = models.CharField(max_length=80, blank=True, help_text="e.g. 7 days")
    instructions = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.medication} {self.dosage}"
