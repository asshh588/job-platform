from django.utils import timezone
from jobs.models import Job


class JadaratService:
    SOURCE = "jadarat"

    def fetch_jobs(self):
        return [
            {
                "external_id": "jadarat-123",
                "title": "مهندس برمجيات",
                "company": "وزارة الاتصالات",
                "location": "RIYADH",
                "url": "https://jadarat.sa/job/123",
            },
            {
                "external_id": "jadarat-456",
                "title": "محلل نظم",
                "company": "وزارة الصحة",
                "location": "JEDDAH",
                "url": "https://jadarat.sa/job/456",
            },
        ]

    def save_jobs(self):
        for job in self.fetch_jobs():
            Job.objects.get_or_create(
                external_id=job["external_id"],
                defaults={
                    "title": job["title"],
                    "company": job["company"],
                    "location": job["location"],
                    "source": self.SOURCE,
                    "url": job["url"],
                    "posted_at": timezone.now().date(),
                },
            )
