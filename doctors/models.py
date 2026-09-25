from datetime import time

from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Doctor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="doctors")
    specialization = models.CharField(max_length=120)
    qualification = models.CharField(max_length=200, blank=True)
    license_number = models.CharField(max_length=50, unique=True)
    experience_years = models.PositiveIntegerField(default=0)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    available_from = models.TimeField(default=time(9, 0))
    available_to = models.TimeField(default=time(17, 0))
    is_available = models.BooleanField(default=True, help_text="Untick to stop accepting new appointments.")
    bio = models.TextField(blank=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    @property
    def full_name(self):
        return f"Dr. {self.user.display_name}"

    def __str__(self):
        return f"{self.full_name} ({self.specialization})"
