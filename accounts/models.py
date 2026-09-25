from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Single user table; the `role` field drives every permission check."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        DOCTOR = "DOCTOR", "Doctor"
        RECEPTIONIST = "RECEPTIONIST", "Receptionist"
        PATIENT = "PATIENT", "Patient"

    role = models.CharField(max_length=15, choices=Role.choices, default=Role.PATIENT)
    phone = models.CharField(max_length=20, blank=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_hospital_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_doctor(self):
        return self.role == self.Role.DOCTOR

    @property
    def is_receptionist(self):
        return self.role == self.Role.RECEPTIONIST

    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT

    def __str__(self):
        return f"{self.display_name} ({self.get_role_display()})"
