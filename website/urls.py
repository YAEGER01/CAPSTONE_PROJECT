from django.urls import path

from . import views


urlpatterns = [
    path("", views.home_view, name="home"),
    path("login/", views.portal_login_view, name="portal-login"),
    path("about/", views.about_view, name="about"),
    path("members/", views.members_view, name="members"),
    path("contact/", views.contact_view, name="contact"),
]
