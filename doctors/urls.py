from django.urls import path

from . import views

app_name = "doctors"
urlpatterns = [
    path("", views.doctor_list, name="list"),
    path("new/", views.doctor_create, name="create"),
    path("<int:pk>/", views.doctor_detail, name="detail"),
    path("<int:pk>/edit/", views.doctor_edit, name="edit"),
    path("<int:pk>/delete/", views.doctor_delete, name="delete"),
    path("departments/", views.department_list, name="departments"),
    path("departments/new/", views.department_create, name="department_create"),
    path("departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
    path("departments/<int:pk>/delete/", views.department_delete, name="department_delete"),
]
