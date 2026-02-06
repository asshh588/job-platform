from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Job


def job_list(request):
    q = request.GET.get("q", "")
    source = request.GET.get("source", "")

    jobs = Job.objects.filter(is_active=True).order_by("-created_at")

    if q:
        jobs = jobs.filter(title__icontains=q)

    if source:
        jobs = jobs.filter(source=source)

    paginator = Paginator(jobs, 9)  # 9 وظائف في الصفحة
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "jobs": page_obj,      # استخدمه في القالب كـ jobs
        "page_obj": page_obj,  # للـ pagination
        "q": q,
        "source": source,
    }
    return render(request, "jobs/job_list.html", context)


def job_detail(request, slug):
    job = get_object_or_404(Job, slug=slug, is_active=True)
    return render(request, "jobs/job_detail.html", {"job": job})
from django.shortcuts import render

def about(request):
    return render(request, "about.html")
