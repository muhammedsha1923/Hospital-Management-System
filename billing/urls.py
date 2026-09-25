from django.urls import path

from . import views

app_name = "billing"
urlpatterns = [
    path("", views.bill_list, name="list"),
    path("new/", views.bill_create, name="create"),
    path("<int:pk>/", views.bill_detail, name="detail"),
    path("<int:pk>/edit/", views.bill_edit, name="edit"),
    path("<int:pk>/print/", views.bill_print, name="print"),
    path("<int:pk>/pay/", views.add_payment, name="pay"),
    path("<int:pk>/delete/", views.bill_delete, name="delete"),
]
