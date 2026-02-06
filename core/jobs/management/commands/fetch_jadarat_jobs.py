from django.core.management.base import BaseCommand
from jobs.models import Job
import feedparser


def split_title_company(raw_title: str):
    t = (raw_title or "").strip()

    # شكل: Company: Job Title
    if ":" in t:
        left, right = t.split(":", 1)
        if len(left) <= 40 and len(right) >= 6:
            return right.strip(), left.strip()

    # شكل: Job Title at Company
    if " at " in t.lower():
        parts = t.rsplit(" at ", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

    return t, "—"


class Command(BaseCommand):
    help = "Fetch jobs from RSS feed (test source)"

    def handle(self, *args, **options):
        feed_url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"RSS failed: {e}"))
            return

        if getattr(feed, "bozo", 0):
            self.stdout.write(self.style.WARNING("RSS parse warning (bozo=1). Continuing..."))

        created = 0
        updated = 0

        for entry in feed.entries:
            raw_title = entry.get("title", "").strip()
            title, company = split_title_company(raw_title)
            url = entry.get("link", "").strip()

            if not title or not url:
                continue

            external_id = url  # نستخدم الرابط كـ ID

            job, was_created = Job.objects.update_or_create(
                source="rss_wrw",
                external_id=external_id,
                defaults={
                    "title": title,
                    "company": company,
                    "location": "Remote",
                    "url": url,
                    "is_active": True,
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"RSS fetch done. created={created}, updated={updated}"
            )
        )
