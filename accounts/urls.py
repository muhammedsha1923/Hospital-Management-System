from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.HospitalLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("password/", views.ChangePasswordView.as_view(), name="password_change"),
    path("users/", views.user_list, name="user_list"),
    path("users/new/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/toggle/", views.user_toggle_active, name="user_toggle"),
]
