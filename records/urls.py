from django.urls import path

from . import views

app_name = "records"
urlpatterns = [
    path("mine/", views.my_records, name="mine"),
    path("new/<int:patient_pk>/", views.record_create, name="create"),
    path("<int:pk>/", views.record_detail, name="detail"),
    path("<int:pk>/edit/", views.record_edit, name="edit"),
]
