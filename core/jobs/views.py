from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce
from django.db.models import DateTimeField
from .models import Job


def job_list(request):
    q = request.GET.get("q", "")
    source = request.GET.get("source", "")

    jobs = (
        Job.objects
        .filter(is_active=True)
        .annotate(
            sort_date=Coalesce(
                "posted_at",
                "created_at",
                output_field=DateTimeField()
            )
        )
        .order_by("-sort_date")
    )

    if q:
        jobs = jobs.filter(title__icontains=q)

    if source:
        jobs = jobs.filter(source=source)

    paginator = Paginator(jobs, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "jobs/job_list.html", {
        "jobs": page_obj,
        "page_obj": page_obj,
        "q": q,
        "source": source,
    })


def job_detail(request, slug):
    job = get_object_or_404(Job, slug=slug, is_active=True)
    return render(request, "jobs/job_detail.html", {"job": job})


def about(request):
    return render(request, "about.html")
