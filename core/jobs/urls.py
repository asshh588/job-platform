from django.urls import path
from .views import job_list, job_detail

urlpatterns = [
    path("", job_list, name="job_list"),
    path("job/<int:pk>/", job_detail, name="job_detail"),
]
