from datetime import timedelta
from django.utils import timezone
from celery import shared_task

from jobs.models import Job


@shared_task
def cleanup_old_jobs(days=7):
    """
    تعطيل الوظائف التي لم يتم رؤيتها منذ X أيام
    يعتمد على last_seen_at
    """
    cutoff = timezone.now() - timedelta(days=days)

    qs = Job.objects.filter(
        is_active=True,
        last_seen_at__lt=cutoff
    )

    disabled_count = qs.count()

    qs.update(is_active=False)

    return {
        "disabled_jobs": disabled_count,
        "older_than_days": days,
    }
