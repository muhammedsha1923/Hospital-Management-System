from django.contrib import admin

from .models import MedicalRecord, Prescription


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 0


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "visit_date")
    inlines = [PrescriptionInline]
