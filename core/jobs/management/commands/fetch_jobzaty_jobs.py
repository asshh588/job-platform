# jobs/management/commands/fetch_jobzaty_jobs.py

import re
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from jobs.models import Job
from jobs.tasks import generate_ai_job_summary


BASE_URL = "https://www.jobzaty.com"
LIST_PATH = "/jobs"


# =========================
# Helpers
# =========================

def _clean_text(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").strip())


def build_list_url(page: int) -> str:
    return f"{BASE_URL}{LIST_PATH}?page={page}"


def extract_posted_date_from_jsonld(soup):
    """
    استخراج تاريخ النشر من JSON-LD
    يدعم:
    - datePosted
    - datePublished
    """
    for s in soup.find_all("script", type="application/ld+json"):
        text = s.string
        if not text:
            continue

        m = re.search(
            r'"date(Post(ed)?|Published)"\s*:\s*"([^"]+)"',
            text,
        )
        if not m:
            continue

        raw_date = m.group(3)

        try:
            # مثال: 2024-01-26
            if len(raw_date) == 10:
                return datetime.strptime(raw_date, "%Y-%m-%d").date()

            # مثال: 2024-01-26T00:00:00+03:00
            return datetime.fromisoformat(raw_date.replace("Z", "")).date()
        except Exception:
            continue

    return None


# =========================
# Extractors
# =========================

def extract_apply_url(session, soup):
    def is_blog(u):
        return "/blog/" in (u or "").lower()

    def is_denied(u):
        deny = [
            "twitter.com", "x.com", "facebook.com", "instagram.com",
            "t.me", "telegram.me", "wa.me", "whatsapp.com",
            "snapchat.com", "tiktok.com", "youtube.com",
        ]
        low = (u or "").lower()
        return any(d in low for d in deny)

    candidates = []

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        abs_url = urljoin(BASE_URL, href)

        if is_blog(abs_url) or is_denied(abs_url):
            continue

        text = _clean_text(a.get_text(" ", strip=True)).lower()
        if not any(k in text for k in ["التقديم", "قدم", "apply"]):
            continue

        score = 0
        if "linkedin.com/jobs/view/" in abs_url.lower():
            score += 50
        if "jobzaty.com" not in abs_url.lower():
            score += 20
        if a.get("target") == "_blank":
            score += 5

        candidates.append((score, abs_url))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def extract_job_description(soup):
    container = soup.select_one(
        "div.job-description, div.content, article, section"
    )
    if not container:
        return ""

    return container.get_text(separator="\n", strip=True)[:8000]


# =========================
# Job Detail
# =========================

def parse_job_detail(session, job_url, timeout=25):
    r = session.get(job_url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    h1 = soup.find("h1")
    title = _clean_text(h1.get_text(strip=True)) if h1 else ""
    if not title:
        return None

    company = ""
    img = soup.find("img", alt=True)
    if img:
        company = _clean_text(img.get("alt", ""))

    posted_at = extract_posted_date_from_jsonld(soup)
    apply_url = extract_apply_url(session, soup)
    description = extract_job_description(soup)

    return {
        "title": title,
        "company": company or "غير محدد",
        "location": "",
        "url": job_url,
        "apply_url": apply_url,
        "description": description,
        "posted_at": posted_at,
    }


# =========================
# Fetcher
# =========================

def fetch_jobzaty_jobs(pages=1, sleep_seconds=1.0, timeout=25, debug=False):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 JobPlatformBot",
        "Accept-Language": "ar,en;q=0.9",
    })

    for page in range(1, pages + 1):
        soup = BeautifulSoup(
            session.get(build_list_url(page), timeout=timeout).text,
            "html.parser",
        )

        job_links = {
            urljoin(BASE_URL, a["href"])
            for a in soup.select("a[href]")
            if "/job/" in a["href"]
        }

        jobs_data = []
        for job_url in job_links:
            try:
                data = parse_job_detail(session, job_url, timeout)
                if data:
                    jobs_data.append(data)
            except Exception:
                continue

        with transaction.atomic():
            for j in jobs_data:
                obj, created = Job.objects.update_or_create(
                    source=Job.Source.JOBZATY,
                    url=j["url"],
                    defaults={
                        "title": j["title"],
                        "company": j["company"],
                        "location": j["location"],
                        "apply_url": j["apply_url"],
                        "description": j["description"],
                        "posted_at": j["posted_at"],
                        "is_active": True,
                        "last_seen_at": timezone.now(),
                    },
                )

                if created or not obj.ai_summary:
                    generate_ai_job_summary.delay(obj.id)

        time.sleep(sleep_seconds)


# =========================
# Django Command
# =========================

class Command(BaseCommand):
    help = "Fetch jobs from JobZaty"

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=1)

    def handle(self, *args, **options):
        self.stdout.write("Fetching JobZaty jobs...")
        fetch_jobzaty_jobs(pages=options["pages"])
        self.stdout.write(self.style.SUCCESS("Done"))
