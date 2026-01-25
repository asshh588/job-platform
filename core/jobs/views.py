from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Job


def job_list(request):
    q = request.GET.get("q", "")
    source = request.GET.get("source", "")

    jobs = Job.objects.all().order_by("-created_at")

    if q:
        jobs = jobs.filter(title__icontains=q)

    if source:
        jobs = jobs.filter(source=source)

    paginator = Paginator(jobs, 9)  # 9 وظائف في الصفحة
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "jobs": page_obj,
        "page_obj": page_obj,
        "q": q,
        "source": source,
    }
    return render(request, "jobs/job_list.html", context)


def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)

    return render(request, "jobs/job_detail.html", {
        "job": job
    })
