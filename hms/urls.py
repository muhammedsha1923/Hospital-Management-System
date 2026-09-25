from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("doctors/", include("doctors.urls")),
    path("patients/", include("patients.urls")),
    path("appointments/", include("appointments.urls")),
    path("records/", include("records.urls")),
    path("admissions/", include("admissions.urls")),
    path("billing/", include("billing.urls")),
]
