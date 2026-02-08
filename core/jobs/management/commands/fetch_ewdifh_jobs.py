# jobs/management/commands/fetch_ewdifh_jobs.py

import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from jobs.models import Job
from jobs.tasks import generate_ai_job_summary


BASE_URL = "https://www.ewdifh.com"
LIST_URL = f"{BASE_URL}/category/all-jobs"


# ----------------- Helpers -----------------

def clean(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").strip())


def is_denied_url(u: str) -> bool:
    low = (u or "").lower()
    deny = [
        "twitter.com", "x.com", "facebook.com", "instagram.com",
        "t.me", "telegram.me", "wa.me", "whatsapp.com",
        "snapchat.com", "tiktok.com", "youtube.com",
    ]
    return any(d in low for d in deny)


def extract_date_from_text(text: str):
    """
    يستخرج تاريخ بصيغة DD-MM-YYYY من أي نص
    مثال: وظائف شركات 05-02-2026
    """
    if not text:
        return None

    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", text)
    if not m:
        return None

    day, month, year = map(int, m.groups())
    try:
        return datetime(year, month, day).date()
    except ValueError:
        return None


# ----------------- Detail Parser -----------------

def parse_job_detail(
    session: requests.Session,
    job_url: str,
    timeout: int = 25,
) -> dict | None:
    r = session.get(job_url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # ---------- Title ----------
    h1 = soup.find("h1")
    title = clean(h1.get_text(" ", strip=True)) if h1 else ""
    if not title:
        return None

    # ---------- Company ----------
    company = "غير محدد"
    if h1:
        for el in h1.find_all_next(["h2", "h3", "p", "span", "div"], limit=30):
            t = clean(el.get_text(" ", strip=True))
            if not t or t == title:
                continue
            if any(k in t for k in ["منذ", "دقيقة", "ساعة", "يوم", "الرئيسية", "جميع الوظائف"]):
                continue
            if 2 <= len(t) <= 80:
                company = t
                break

    location = ""

    # ---------- RAW TEXT ----------
    raw_text = ""
    main = soup.find("main")
    if main:
        card_body = main.select_one("div.card-body")
        if card_body:
            raw_text = card_body.get_text(separator="\n", strip=True)

    # ---------- Apply URL ----------
    apply_url = ""
    keywords = [
        "رابط التقديم", "التقديم", "قدّم", "قدم",
        "اضغط هنا", "Apply", "Apply Now",
        "المصدر", "من خلال الرابط التالي",
    ]

    candidates = []
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        txt = clean(a.get_text(" ", strip=True))
        if not txt:
            continue

        if not any(k.lower() in txt.lower() for k in keywords):
            continue

        abs_url = urljoin(BASE_URL, href)
        if is_denied_url(abs_url):
            continue

        low = abs_url.lower()
        if "ewdifh.com" in low and any(x in low for x in ["/category/", "/privacy", "/terms", "/about"]):
            continue

        host = urlparse(abs_url).netloc.lower()
        score = 0
        if host and "ewdifh.com" not in host:
            score += 20
        if a.get("target") == "_blank":
            score += 3

        candidates.append((score, abs_url))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        apply_url = candidates[0][1]

    # ✅ استخراج تاريخ المصدر الحقيقي
    posted_at = extract_date_from_text(company)

    return {
        "title": title,
        "company": company,
        "location": location,
        "url": job_url,
        "apply_url": apply_url,
        "raw_text": raw_text,
        "posted_at": posted_at,
    }


# ----------------- Main Fetcher -----------------

def fetch_ewdifh_jobs(
    pages: int = 1,
    sleep_seconds: float = 1.0,
    timeout: int = 25,
    debug: bool = False,
):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; JobPlatformBot/1.0)",
        "Accept-Language": "ar,en;q=0.9",
    })

    for page in range(1, pages + 1):
        list_url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"

        r = session.get(list_url, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        job_links = set()
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            if href and re.search(r"/jobs/\d+/?$", href):
                job_links.add(urljoin(BASE_URL, href))

        jobs_data = []
        for job_url in job_links:
            try:
                data = parse_job_detail(session, job_url, timeout=timeout)
                if data:
                    jobs_data.append(data)
            except Exception as e:
                if debug:
                    print("DETAIL ERROR:", job_url, e)

        with transaction.atomic():
            for j in jobs_data:
                posted_at = j["posted_at"] or timezone.now().date()

                obj, _ = Job.objects.update_or_create(
                    source=Job.Source.EWDIFH,
                    url=j["url"],
                    defaults={
                        "title": j["title"],
                        "company": j["company"],
                        "location": j["location"],
                        "apply_url": j.get("apply_url", ""),
                        "description": "",
                        "is_active": True,
                        "posted_at": posted_at,   # ✅ تاريخ المصدر الحقيقي
                        "last_seen_at": timezone.now(),
                    },
                )

                if j["raw_text"] and j["raw_text"] != obj.raw_text:
                    obj.raw_text = j["raw_text"]
                    obj.save(update_fields=["raw_text"])

                if obj.raw_text and not obj.ai_summary:
                    generate_ai_job_summary.delay(obj.id)

        if sleep_seconds:
            time.sleep(sleep_seconds)


# ----------------- Django Command -----------------

class Command(BaseCommand):
    help = "Fetch jobs from ewdifh.com with correct source date ordering."

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=1)
        parser.add_argument("--sleep", type=float, default=1.0)
        parser.add_argument("--timeout", type=int, default=25)

    def handle(self, *args, **options):
        fetch_ewdifh_jobs(
            pages=options["pages"],
            sleep_seconds=options["sleep"],
            timeout=options["timeout"],
        )
        self.stdout.write(self.style.SUCCESS("Done."))
