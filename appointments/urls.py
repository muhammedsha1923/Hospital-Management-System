from django.urls import path

from . import views

app_name = "appointments"
urlpatterns = [
    path("", views.appointment_list, name="list"),
    path("new/", views.appointment_create, name="create"),
    path("slots/", views.free_slots, name="slots"),
    path("<int:pk>/", views.appointment_detail, name="detail"),
    path("<int:pk>/edit/", views.appointment_edit, name="edit"),
    path("<int:pk>/status/", views.appointment_status, name="status"),
    path("<int:pk>/check-in/", views.appointment_checkin, name="checkin"),
]
