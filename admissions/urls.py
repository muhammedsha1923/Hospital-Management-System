from django.urls import path

from . import views

app_name = "admissions"
urlpatterns = [
    path("", views.admission_list, name="list"),
    path("admit/", views.admit, name="admit"),
    path("<int:pk>/discharge/", views.discharge, name="discharge"),
    path("beds/", views.bed_list, name="beds"),
    path("beds/new/", views.bed_create, name="bed_create"),
    path("beds/<int:pk>/edit/", views.bed_edit, name="bed_edit"),
    path("beds/<int:pk>/delete/", views.bed_delete, name="bed_delete"),
]
