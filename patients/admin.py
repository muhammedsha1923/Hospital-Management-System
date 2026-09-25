from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("patient_id", "full_name", "phone", "blood_group")
    search_fields = ("first_name", "last_name", "patient_id", "phone")
