from django.core.management.base import BaseCommand
from jobs.services.jadarat_service import JadaratService


class Command(BaseCommand):
    help = "Fetch jobs from Jadarat (mock data)"

    def handle(self, *args, **options):
        service = JadaratService()
        service.save_jobs()

        self.stdout.write(
            self.style.SUCCESS("✅ Jadarat jobs fetched successfully")
        )
