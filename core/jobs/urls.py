from django.urls import path
from .views import job_list, job_detail
from . import views

urlpatterns = [
    path("", job_list, name="job_list"),
    path("job/<slug:slug>/", job_detail, name="job_detail"),
    path("about/", views.about, name="about"),
]
