from django.urls import path

from . import views

app_name = "patients"
urlpatterns = [
    path("", views.patient_list, name="list"),
    path("new/", views.patient_create, name="create"),
    path("me/", views.my_profile, name="me"),
    path("<int:pk>/", views.patient_detail, name="detail"),
    path("<int:pk>/edit/", views.patient_edit, name="edit"),
    path("<int:pk>/delete/", views.patient_delete, name="delete"),
]
