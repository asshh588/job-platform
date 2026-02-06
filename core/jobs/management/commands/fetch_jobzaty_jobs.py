# jobs/management/commands/fetch_jobzaty_jobs.py

import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.db import transaction

from jobs.models import Job


BASE_URL = "https://www.jobzaty.com"
LIST_PATH = "/jobs"


def _clean_text(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").strip())


def build_list_url(page: int) -> str:
    return f"{BASE_URL}{LIST_PATH}?page={page}"


def extract_apply_url(session, soup, timeout=20):
    """
    استخراج رابط التقديم الحقيقي من صفحة JobZaty
    مع استبعاد السوشال والـ blog
    """

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
        if not any(k in text for k in ["التقديم", "قدم", "اضغط", "apply", "source"]):
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


def parse_job_detail(session, job_url, timeout=25):
    r = session.get(job_url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Title
    h1 = soup.find("h1")
    title = _clean_text(h1.get_text(strip=True)) if h1 else ""
    if not title:
        return None

    # Company
    company = ""
    img = soup.find("img", alt=True)
    if img:
        company = _clean_text(img.get("alt", ""))

    if not company:
        for el in soup.find_all(["h2", "h3", "p", "span", "div"], limit=40):
            t = _clean_text(el.get_text(" ", strip=True))
            if t and t != title and len(t) <= 80:
                company = t
                break

    # Location (بسيط)
    location = ""

    apply_url = extract_apply_url(session, soup, timeout)

    return {
        "title": title,
        "company": company or "غير محدد",
        "location": location,
        "url": job_url,
        "apply_url": apply_url,
    }


def fetch_jobzaty_jobs(pages=1, sleep_seconds=1.0, timeout=25, debug=False):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 JobPlatformBot",
        "Accept-Language": "ar,en;q=0.9",
    })

    summary = {
        "fetched_pages": 0,
        "list_job_links": 0,
        "parsed_jobs": 0,
        "created": 0,
        "updated": 0,
        "errors": [],
    }

    for page in range(1, pages + 1):
        list_url = build_list_url(page)

        try:
            r = session.get(list_url, timeout=timeout)
            r.raise_for_status()
        except Exception as e:
            summary["errors"].append({"stage": "list", "page": page, "error": str(e)})
            continue

        summary["fetched_pages"] += 1
        soup = BeautifulSoup(r.text, "html.parser")

        job_links = set()
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            if "/job/" in href:
                job_links.add(urljoin(BASE_URL, href))

        summary["list_job_links"] += len(job_links)

        if debug:
            print(f"[DEBUG] page={page} job_links={len(job_links)}")

        jobs_data = []
        for job_url in job_links:
            try:
                data = parse_job_detail(session, job_url, timeout)
                if data:
                    jobs_data.append(data)
            except Exception as e:
                summary["errors"].append({"stage": "detail", "url": job_url, "error": str(e)})

        summary["parsed_jobs"] += len(jobs_data)

        with transaction.atomic():
            for j in jobs_data:
                obj, created = Job.objects.update_or_create(
                    source="jobzaty",
                    url=j["url"],
                    defaults={
                        "title": j["title"],
                        "company": j["company"],
                        "location": j["location"],
                        "apply_url": j["apply_url"],
                    },
                )
                summary["created"] += int(created)
                summary["updated"] += int(not created)

        time.sleep(sleep_seconds)

    return summary


class Command(BaseCommand):
    help = "Fetch jobs from JobZaty"

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=1)
        parser.add_argument("--sleep", type=float, default=1.0)
        parser.add_argument("--timeout", type=int, default=25)
        parser.add_argument("--debug", action="store_true")

    def handle(self, *args, **options):
        self.stdout.write("Fetching JobZaty jobs...")
        res = fetch_jobzaty_jobs(
            pages=options["pages"],
            sleep_seconds=options["sleep"],
            timeout=options["timeout"],
            debug=options["debug"],
        )
        self.stdout.write(self.style.SUCCESS(str(res)))
