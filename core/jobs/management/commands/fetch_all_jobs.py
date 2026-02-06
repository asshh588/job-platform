# jobs/management/commands/fetch_all_jobs.py

from django.core.management.base import BaseCommand

# استيراد دوال الفتش من نفس أوامر الإدارة
from jobs.management.commands.fetch_jobzaty_jobs import fetch_jobzaty_jobs
from jobs.management.commands.fetch_ewdifh_jobs import fetch_ewdifh_jobs

# إذا تبغى تضيف جدارات لاحقًا:
# from jobs.management.commands.fetch_jadarat_jobs import fetch_jadarat_jobs


class Command(BaseCommand):
    help = "Fetch jobs from all sources (JobZaty + Ewdifh) in one command."

    def add_arguments(self, parser):
        # JobZaty
        parser.add_argument("--jobzaty-pages", type=int, default=1)
        parser.add_argument("--jobzaty-sleep", type=float, default=1.0)
        parser.add_argument("--jobzaty-timeout", type=int, default=25)
        parser.add_argument("--jobzaty-debug", action="store_true")

        # Ewdifh
        parser.add_argument("--ewdifh-pages", type=int, default=1)
        parser.add_argument("--ewdifh-sleep", type=float, default=1.0)
        parser.add_argument("--ewdifh-timeout", type=int, default=25)
        parser.add_argument("--ewdifh-debug", action="store_true")

        # تشغيل/إيقاف مصادر
        parser.add_argument("--only", choices=["jobzaty", "ewdifh", "all"], default="all")
        parser.add_argument("--stop-on-error", action="store_true", help="Stop if any source fails")

    def handle(self, *args, **options):
        only = options["only"]
        stop_on_error = bool(options["stop_on_error"])

        results = {}

        def run_source(name, fn, kwargs):
            self.stdout.write(self.style.MIGRATE_HEADING(f"==> Running {name} ..."))
            try:
                res = fn(**kwargs)
                results[name] = {"ok": True, "summary": res}
                self.stdout.write(self.style.SUCCESS(f"==> {name} done ✅"))
            except Exception as e:
                results[name] = {"ok": False, "error": str(e)}
                self.stdout.write(self.style.ERROR(f"==> {name} failed ❌: {e}"))
                if stop_on_error:
                    raise

        if only in ("jobzaty", "all"):
            run_source(
                "jobzaty",
                fetch_jobzaty_jobs,
                dict(
                    pages=max(1, int(options["jobzaty_pages"])),
                    sleep_seconds=max(0.0, float(options["jobzaty_sleep"])),
                    timeout=max(5, int(options["jobzaty_timeout"])),
                    debug=bool(options["jobzaty_debug"]),
                ),
            )

        if only in ("ewdifh", "all"):
            run_source(
                "ewdifh",
                fetch_ewdifh_jobs,
                dict(
                    pages=max(1, int(options["ewdifh_pages"])),
                    sleep_seconds=max(0.0, float(options["ewdifh_sleep"])),
                    timeout=max(5, int(options["ewdifh_timeout"])),
                    debug=bool(options["ewdifh_debug"]),
                ),
            )

        # إذا تبغى تضيف جدارات:
        # run_source("jadarah", fetch_jadarat_jobs, {...})

        self.stdout.write(self.style.SUCCESS("\n=== Summary ==="))
        for k, v in results.items():
            if v.get("ok"):
                self.stdout.write(f"- {k}: OK | {v['summary']}")
            else:
                self.stdout.write(f"- {k}: FAIL | {v['error']}")
