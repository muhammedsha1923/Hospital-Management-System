from django.contrib import admin

from .models import Department, Doctor

admin.site.register(Department)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "specialization", "is_available")
    list_filter = ("department", "is_available")
